"""
Sandwich Jackpot — Material Design dark theme poker machine
Takes a photo of your fridge and suggests sandwiches via Claude AI vision.
"""

import os, base64, threading, random, json
from pathlib import Path

from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.graphics import Color, Rectangle, RoundedRectangle, Ellipse, Line
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from plyer import camera as plyer_camera
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False

try:
    from android.permissions import request_permissions, Permission
    from android.storage import primary_external_storage_path
    ANDROID = True
except ImportError:
    ANDROID = False

# ── Material Design Light Palette ─────────────────────────────────────────────
M_BG        = (0.961, 0.961, 0.961, 1)    # #F5F5F5  background
M_SURF      = (1.000, 1.000, 1.000, 1)    # #FFFFFF   surface
M_SURF2     = (0.980, 0.980, 0.980, 1)    # #FAFAFA   elevated surface
M_SURF3     = (0.933, 0.933, 0.933, 1)    # #EEEEEE   highest elevation
M_AMBER     = (0.071, 0.157, 0.420, 1)    # navy blue (replaces amber for text)
M_AMBER_DIM = (0.200, 0.310, 0.580, 1)    # muted navy fill
M_RED       = (0.400, 0.620, 0.800, 1)    # medium pastel blue / spin button
M_RED_DARK  = (0.310, 0.530, 0.720, 1)
M_ON_BG     = (0.129, 0.129, 0.129, 1)    # #212121   primary text
M_ON_DIM    = (0.459, 0.459, 0.459, 1)    # #757575   secondary text
M_SUCCESS   = (0.106, 0.627, 0.278, 1)    # #1BA047   green
M_ERROR     = (0.757, 0.114, 0.082, 1)    # #C11D15
M_WIN       = (0.071, 0.157, 0.420, 1)    # navy for win labels
M_SHADOW    = (0.000, 0.000, 0.000, 0.15)
M_BLACK     = (0.000, 0.000, 0.000, 1)
M_WHITE     = (1.000, 1.000, 1.000, 1)

CARD_R  = dp(20)   # card corner radius
BTN_R   = dp(28)   # button corner radius

ACCENT_DOTS = [
    (0.90, 0.28, 0.28, 1),
    (1.00, 0.76, 0.03, 1),
    (0.40, 0.86, 0.40, 1),
    (0.25, 0.55, 1.00, 1),
    (0.85, 0.40, 1.00, 1),
    (1.00, 0.55, 0.10, 1),
]

SPIN_ITEMS = [
    "🥚 EGGS", "🧀 CHEESE", "🥓 BACON", "🍅 TOMATO",
    "🥬 LETTUCE", "🧅 ONION", "🥑 AVOCADO", "🍗 CHICKEN",
    "🥩 HAM", "🐟 TUNA", "🧄 GARLIC", "🥒 CUCUMBER",
    "🫑 PEPPER", "🫒 OLIVES", "🧈 BUTTER", "🍯 MUSTARD",
    "🥜 P.BUTTER", "🍓 JAM", "🧆 FALAFEL", "🧁 CREAM CH.",
    "🥗 SALAD", "🍖 TURKEY", "💰 LUCKY!", "⭐ WILD!",
]


# ── Helpers ───────────────────────────────────────────────────────────────────
def card(widget, color=M_SURF2, radius=None, shadow=True):
    """Attach a Material card background (shadow + rounded surface) to widget."""
    r = radius or CARD_R
    with widget.canvas.before:
        if shadow:
            Color(*M_SHADOW)
            widget._shadow_rect = RoundedRectangle(radius=[r])
        Color(*color)
        widget._card_rect = RoundedRectangle(radius=[r])

    def _upd(*_):
        if shadow:
            widget._shadow_rect.pos  = (widget.x + dp(3), widget.y - dp(4))
            widget._shadow_rect.size = widget.size
        widget._card_rect.pos  = widget.pos
        widget._card_rect.size = widget.size

    widget.bind(pos=_upd, size=_upd)


def outlined_card(widget, surface=M_SURF2, outline=M_AMBER_DIM, radius=None):
    """Card with a subtle amber outline."""
    r = radius or CARD_R
    with widget.canvas.before:
        Color(*M_SHADOW)
        widget._shadow_rect = RoundedRectangle(radius=[r])
        # Outline layer (1 px larger each side)
        Color(*outline)
        widget._outline_rect = RoundedRectangle(radius=[r])
        Color(*surface)
        widget._fill_rect = RoundedRectangle(radius=[r])

    def _upd(*_):
        pad = dp(2)
        widget._shadow_rect.pos  = (widget.x + dp(3), widget.y - dp(4))
        widget._shadow_rect.size = widget.size
        widget._outline_rect.pos  = (widget.x - pad, widget.y - pad)
        widget._outline_rect.size = (widget.width + pad*2, widget.height + pad*2)
        widget._fill_rect.pos  = widget.pos
        widget._fill_rect.size = widget.size

    widget.bind(pos=_upd, size=_upd)


# ── Reel Widget ───────────────────────────────────────────────────────────────
class ReelWidget(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.spinning = False
        self._spin_event = None
        card(self, color=M_SURF, radius=CARD_R)

        self.item_label = Label(
            text=random.choice(SPIN_ITEMS),
            font_size=sp(80),
            bold=True,
            color=M_AMBER,
            halign='center',
            valign='middle',
        )
        self.add_widget(self.item_label)
        self.bind(pos=self._update, size=self._update)

    def _update(self, *_):
        self.item_label.pos       = self.pos
        self.item_label.size      = self.size
        self.item_label.text_size = self.size

    def start_spinning(self):
        self.spinning = True
        if self._spin_event:
            self._spin_event.cancel()
        self._spin_event = Clock.schedule_interval(self._tick, 0.07)

    def _tick(self, _dt):
        self.item_label.text  = random.choice(SPIN_ITEMS)
        self.item_label.color = random.choice(ACCENT_DOTS)

    def stop_spinning(self, final_item, delay=0.0):
        def _do(*_):
            self.spinning = False
            if self._spin_event:
                self._spin_event.cancel()
            self._slow_stop(final_item, steps=9)
        Clock.schedule_once(_do, delay)

    def _slow_stop(self, final_item, steps=9):
        if steps <= 0:
            self.item_label.text  = final_item
            self.item_label.color = M_WIN
            anim = (Animation(color=M_WIN, duration=0.1) +
                    Animation(color=M_AMBER,   duration=0.15))
            anim.start(self.item_label)
            return
        self.item_label.text  = random.choice(SPIN_ITEMS)
        self.item_label.color = random.choice(ACCENT_DOTS)
        Clock.schedule_once(
            lambda _: self._slow_stop(final_item, steps - 1),
            0.04 + (9 - steps) * 0.05,
        )


# ── Main Layout ───────────────────────────────────────────────────────────────
class SandwichMachineLayout(FloatLayout):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_spinning = False
        self.api_key     = os.environ.get('ANTHROPIC_API_KEY', '')
        self.photo_path  = None
        self.credits     = 10
        self._dot_phase  = 0
        self._build_ui()
        Clock.schedule_interval(self._animate_dots, 0.3)

        if ANDROID:
            request_permissions([
                Permission.CAMERA, Permission.INTERNET,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
            ])

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build_ui(self):
        Window.clearcolor = M_BG

        # Solid background
        with self.canvas.before:
            Color(*M_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd_bg, size=self._upd_bg)

        root = BoxLayout(
            orientation='vertical',
            padding=[dp(16), dp(12)],
            spacing=dp(10),
            pos=self.pos,
            size=self.size,
        )
        self.bind(
            pos=lambda *_: setattr(root, 'pos',  self.pos),
            size=lambda *_: setattr(root, 'size', self.size),
        )

        # ── App bar ──────────────────────────────────────────────────────────
        bar = BoxLayout(orientation='horizontal', size_hint=(1, 0.09), spacing=dp(8))
        card(bar, color=M_SURF, shadow=False)

        bar.add_widget(Label(
            text="🎰",
            font_size=sp(110),
            size_hint=(0.12, 1),
            halign='center',
        ))
        self.title_lbl = Label(
            text="SANDWICH JACKPOT",
            font_size=sp(110),
            bold=True,
            color=M_AMBER,
            halign='left',
            valign='middle',
            size_hint=(0.76, 1),
        )
        self.title_lbl.bind(size=lambda *_: setattr(self.title_lbl, 'text_size', self.title_lbl.size))
        bar.add_widget(self.title_lbl)

        settings_btn = Button(
            text="⚙",
            font_size=sp(90),
            bold=True,
            color=M_ON_DIM,
            background_color=(0, 0, 0, 0),
            background_normal='',
            size_hint=(0.12, 1),
        )
        settings_btn.bind(on_press=self._show_api_dialog)
        bar.add_widget(settings_btn)
        root.add_widget(bar)

        # ── Accent dots strip ─────────────────────────────────────────────────
        dot_row = BoxLayout(orientation='horizontal', size_hint=(1, 0.035), spacing=dp(4))
        self.dots = []
        for i in range(28):
            fl = FloatLayout(size_hint=(1, 1))
            with fl.canvas:
                c_inst = Color(*ACCENT_DOTS[i % len(ACCENT_DOTS)])
                e_inst = Ellipse(pos=(0, 0), size=(dp(1), dp(1)))
            fl._color = c_inst
            fl._ellipse = e_inst
            def _upd_dot(w, *_, _e=e_inst):
                d = min(w.width, w.height) * 0.7
                _e.size = (d, d)
                _e.pos  = (w.x + (w.width  - d) / 2,
                           w.y + (w.height - d) / 2)
            fl.bind(pos=_upd_dot, size=_upd_dot)
            self.dots.append((fl, c_inst))
            dot_row.add_widget(fl)
        root.add_widget(dot_row)

        # ── Reels ─────────────────────────────────────────────────────────────
        reels_panel = BoxLayout(orientation='vertical', size_hint=(1, 0.33), spacing=dp(4))

        reel_labels = BoxLayout(orientation='horizontal', size_hint=(1, 0.20), spacing=dp(10))
        for txt in ["INGREDIENT  1", "INGREDIENT  2", "INGREDIENT  3"]:
            lbl = Label(text=txt, font_size=sp(50), bold=True, color=M_ON_DIM, halign='center')
            reel_labels.add_widget(lbl)
        reels_panel.add_widget(reel_labels)

        reels_row = BoxLayout(orientation='horizontal', size_hint=(1, 0.80), spacing=dp(10))
        self.reels = [ReelWidget(size_hint=(1, 1)) for _ in range(3)]
        for r in self.reels:
            reels_row.add_widget(r)
        reels_panel.add_widget(reels_row)
        root.add_widget(reels_panel)

        # ── Result card ───────────────────────────────────────────────────────
        result_card = BoxLayout(orientation='vertical', size_hint=(1, 0.20),
                                spacing=dp(4), padding=[dp(10), dp(6)])
        outlined_card(result_card, surface=M_SURF2, outline=M_AMBER_DIM)

        self.result_lbl = Label(
            text="INSERT COIN  →  TAP SPIN TO TAKE A PHOTO",
            font_size=sp(60),
            bold=True,
            color=M_ON_DIM,
            halign='center',
            valign='middle',
        )
        self.result_lbl.bind(size=lambda *_: setattr(self.result_lbl, 'text_size', self.result_lbl.size))

        self.sandwich_lbl = Label(
            text="🥪  ???  🥪",
            font_size=sp(100),
            bold=True,
            color=M_AMBER,
            halign='center',
            valign='middle',
        )
        self.sandwich_lbl.bind(size=lambda *_: setattr(self.sandwich_lbl, 'text_size', self.sandwich_lbl.size))

        result_card.add_widget(self.result_lbl)
        result_card.add_widget(self.sandwich_lbl)
        root.add_widget(result_card)

        # ── Bottom dot strip ──────────────────────────────────────────────────
        dot_row2 = BoxLayout(orientation='horizontal', size_hint=(1, 0.035), spacing=dp(4))
        self.dots2 = []
        for i in range(28):
            fl = FloatLayout(size_hint=(1, 1))
            with fl.canvas:
                c_inst = Color(*ACCENT_DOTS[(i + 3) % len(ACCENT_DOTS)])
                e_inst = Ellipse(pos=(0, 0), size=(dp(1), dp(1)))
            fl._color = c_inst
            fl._ellipse = e_inst
            def _upd_dot2(w, *_, _e=e_inst):
                d = min(w.width, w.height) * 0.7
                _e.size = (d, d)
                _e.pos  = (w.x + (w.width  - d) / 2,
                           w.y + (w.height - d) / 2)
            fl.bind(pos=_upd_dot2, size=_upd_dot2)
            self.dots2.append((fl, c_inst))
            dot_row2.add_widget(fl)
        root.add_widget(dot_row2)

        # ── Action button ─────────────────────────────────────────────────────
        btn_row = BoxLayout(orientation='horizontal', size_hint=(1, 0.17))

        self.spin_btn = Button(
            text="📸   SPIN  /  TAKE PHOTO",
            font_size=sp(75),
            bold=True,
            color=M_WHITE,
            background_color=(0, 0, 0, 0),
            background_normal='',
            size_hint=(1, 1),
        )
        card(self.spin_btn, color=M_RED, radius=BTN_R)
        self.spin_btn.bind(on_press=self._on_spin)

        btn_row.add_widget(self.spin_btn)
        root.add_widget(btn_row)

        # ── Status chips ──────────────────────────────────────────────────────
        chips_row = BoxLayout(orientation='horizontal', size_hint=(1, 0.07), spacing=dp(8))

        self.credits_lbl = self._make_chip(f"CREDITS  {self.credits}", M_AMBER)
        self.status_lbl  = self._make_chip("READY", M_SUCCESS)
        self.last_lbl    = self._make_chip("LAST: ???", M_ON_DIM)

        chips_row.add_widget(self.credits_lbl)
        chips_row.add_widget(self.status_lbl)
        chips_row.add_widget(self.last_lbl)
        root.add_widget(chips_row)

        self.add_widget(root)

    def _make_chip(self, text, color):
        lbl = Label(
            text=text,
            font_size=sp(55),
            bold=True,
            color=color,
            halign='center',
            valign='middle',
        )
        card(lbl, color=M_SURF3, radius=dp(30), shadow=False)
        lbl.bind(size=lambda *_: setattr(lbl, 'text_size', lbl.size))
        return lbl

    # ── Background ────────────────────────────────────────────────────────────
    def _upd_bg(self, *_):
        self._bg.pos  = self.pos
        self._bg.size = self.size

    # ── Dot animation ─────────────────────────────────────────────────────────
    def _animate_dots(self, _dt):
        self._dot_phase = (self._dot_phase + 1) % len(ACCENT_DOTS)
        for i, (_, c) in enumerate(self.dots):
            col = ACCENT_DOTS[(i + self._dot_phase) % len(ACCENT_DOTS)]
            c.rgba = col
        for i, (_, c) in enumerate(self.dots2):
            col = ACCENT_DOTS[(len(self.dots2) - i + self._dot_phase) % len(ACCENT_DOTS)]
            c.rgba = col
        # Pulse title
        self.title_lbl.color = M_AMBER if self._dot_phase % 2 == 0 else M_WIN

    def _fast_dots(self, fast=True):
        Clock.unschedule(self._animate_dots)
        Clock.schedule_interval(self._animate_dots, 0.07 if fast else 0.3)

    # ── Spin ──────────────────────────────────────────────────────────────────
    def _on_spin(self, *_):
        if self.is_spinning:
            return
        if not self.api_key:
            self._show_api_dialog()
            return
        self._take_photo()

    # ── Camera ────────────────────────────────────────────────────────────────
    def _take_photo(self):
        base = primary_external_storage_path() if ANDROID else os.path.expanduser('~')
        self.photo_path = os.path.join(base, 'sandwich_photo.jpg')
        if PLYER_AVAILABLE:
            try:
                plyer_camera.take_picture(filename=self.photo_path,
                                          on_complete=self._on_photo_taken)
            except Exception as exc:
                self._show_error(f"Camera error: {exc}")
        else:
            self._demo_mode()

    def _on_photo_taken(self, filename):
        if filename:
            self.photo_path = filename
            Clock.schedule_once(lambda _: self._start_analysis(), 0)
        else:
            Clock.schedule_once(lambda _: self._show_error("Photo cancelled"), 0)

    # ── Demo mode ─────────────────────────────────────────────────────────────
    def _demo_mode(self):
        self.status_lbl.text  = "DEMO MODE"
        self.status_lbl.color = M_AMBER
        self._start_spinning_ui()
        Clock.schedule_once(lambda _: self._show_results({
            "sandwich": "Classic BLT",
            "ingredients": ["🥓 BACON", "🥬 LETTUCE", "🍅 TOMATO"],
            "recipe": "Stack crispy bacon, fresh lettuce and tomato on toasted bread with mayo.",
            "alternatives": ["Club Sandwich", "Turkey BLT"],
        }), 3.5)

    # ── Analysis ──────────────────────────────────────────────────────────────
    def _start_analysis(self):
        self._start_spinning_ui()
        threading.Thread(target=self._analyze_photo, daemon=True).start()

    def _start_spinning_ui(self):
        self.is_spinning = True
        self.spin_btn.disabled = True
        # Dim the spin button card
        self.spin_btn._card_rect.rgba = M_RED_DARK
        self.result_lbl.text  = "ANALYZING YOUR FRIDGE…"
        self.result_lbl.color = M_AMBER
        self.sandwich_lbl.text = "🎰  SPINNING…  🎰"
        self.status_lbl.text  = "ANALYZING…"
        self.status_lbl.color = M_AMBER
        for reel in self.reels:
            reel.start_spinning()
        self._fast_dots(True)

    def _analyze_photo(self):
        try:
            with open(self.photo_path, 'rb') as fh:
                img_b64 = base64.standard_b64encode(fh.read()).decode()
            ext        = Path(self.photo_path).suffix.lower()
            media_type = {'.jpg':'image/jpeg','.jpeg':'image/jpeg',
                          '.png':'image/png','.webp':'image/webp'}.get(ext,'image/jpeg')

            client = anthropic.Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=512,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image",
                         "source": {"type": "base64", "media_type": media_type, "data": img_b64}},
                        {"type": "text",
                         "text": (
                             "Look at this fridge photo and identify ingredients. "
                             "Respond ONLY with valid JSON — no markdown, no extra text:\n"
                             '{"sandwich":"Name of best sandwich","ingredients":'
                             '["🥚 EGGS","🧀 CHEESE","🥩 HAM"],'
                             '"recipe":"One-sentence recipe.",'
                             '"alternatives":["Alt 1","Alt 2"]}\n'
                             "Use exactly 3 items in ingredients, each with a food emoji in ALL CAPS."
                         )},
                    ],
                }],
            )

            raw = response.content[0].text.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result = json.loads(raw.strip())
            Clock.schedule_once(lambda _: self._show_results(result), 0)

        except json.JSONDecodeError as exc:
            Clock.schedule_once(lambda _: self._show_error(f"Parse error: {exc}"), 0)
        except Exception as exc:
            Clock.schedule_once(lambda _: self._show_error(str(exc)), 0)

    # ── Results ───────────────────────────────────────────────────────────────
    def _show_results(self, result):
        ingredients = result.get("ingredients", ["🥚 EGGS", "🧀 CHEESE", "🥩 HAM"])
        while len(ingredients) < 3:
            ingredients.append("🥗 SALAD")
        ingredients = ingredients[:3]
        sandwich = result.get("sandwich", "Mystery Sandwich")
        recipe   = result.get("recipe",   "A delicious creation!")

        for i, (reel, ing) in enumerate(zip(self.reels, ingredients)):
            reel.stop_spinning(ing, delay=i * 0.9)

        def _reveal(*_):
            self.sandwich_lbl.text  = f"🥪  {sandwich.upper()}  🥪"
            self.sandwich_lbl.color = M_AMBER
            self.result_lbl.text    = recipe
            self.result_lbl.color   = M_ON_BG
            self.status_lbl.text    = "★  JACKPOT!"
            self.status_lbl.color   = M_SUCCESS
            self.last_lbl.text      = f"LAST: {sandwich[:16]}"
            self.last_lbl.color     = M_AMBER
            self.credits           += 5
            self.credits_lbl.text   = f"CREDITS  {self.credits}"
            self.spin_btn.disabled           = False
            self.spin_btn._card_rect.rgba    = M_RED
            self.is_spinning                 = False
            self._fast_dots(False)
            self._jackpot_flash(5)

        Clock.schedule_once(_reveal, 4.0)

    def _jackpot_flash(self, n):
        if n <= 0:
            return
        with self.canvas:
            Color(1.0, 0.85, 0.0, 0.18)
            flash = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(0)])

        def _clear(*_):
            self.canvas.remove(flash)
            Clock.schedule_once(lambda _: self._jackpot_flash(n - 1), 0.13)

        Clock.schedule_once(_clear, 0.13)

    # ── Error ─────────────────────────────────────────────────────────────────
    def _show_error(self, msg):
        self.result_lbl.text            = f"⚠  {msg}"
        self.result_lbl.color           = M_ERROR
        self.sandwich_lbl.text          = "TRY AGAIN"
        self.sandwich_lbl.color         = M_ERROR
        self.status_lbl.text            = "ERROR"
        self.status_lbl.color           = M_ERROR
        self.spin_btn.disabled          = False
        self.spin_btn._card_rect.rgba   = M_RED
        self.is_spinning                = False
        for reel in self.reels:
            reel.stop_spinning("❌ ERROR", delay=0)
        self._fast_dots(False)

    # ── API Key dialog ────────────────────────────────────────────────────────
    def _show_api_dialog(self, *_):
        content = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(16))

        content.add_widget(Label(
            text="Anthropic API Key",
            font_size=sp(70), bold=True, color=M_AMBER,
            size_hint=(1, 0.2), halign='center',
        ))

        key_input = TextInput(
            text=self.api_key,
            hint_text="sk-ant-...",
            multiline=False,
            password=True,
            font_size=sp(65),
            foreground_color=M_ON_BG,
            background_color=M_SURF3,
            cursor_color=M_AMBER,
            size_hint=(1, 0.3),
        )
        content.add_widget(key_input)

        content.add_widget(Label(
            text="console.anthropic.com",
            font_size=sp(55), color=M_ON_DIM,
            size_hint=(1, 0.18), halign='center',
        ))

        popup = Popup(
            title="API Key",
            title_color=M_AMBER,
            title_size=sp(70),
            content=content,
            size_hint=(0.90, 0.50),
            background_color=M_SURF,
            separator_color=M_AMBER_DIM,
        )

        def _save(*_):
            self.api_key = key_input.text.strip()
            popup.dismiss()
            if self.api_key:
                self.status_lbl.text  = "KEY SAVED ✓"
                self.status_lbl.color = M_SUCCESS

        save_btn = Button(
            text="SAVE",
            font_size=sp(70), bold=True,
            color=M_BLACK,
            background_color=(0, 0, 0, 0),
            background_normal='',
            size_hint=(1, 0.25),
        )
        card(save_btn, color=M_AMBER, radius=BTN_R)
        save_btn.bind(on_press=_save)
        content.add_widget(save_btn)
        popup.open()


# ── App ───────────────────────────────────────────────────────────────────────
class SandwichJackpotApp(App):
    def build(self):
        self.title = "Sandwich Jackpot"
        return SandwichMachineLayout()


if __name__ == "__main__":
    SandwichJackpotApp().run()
