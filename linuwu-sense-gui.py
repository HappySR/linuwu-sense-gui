#!/usr/bin/env python3
"""GTK4 control panel for Linuwu-Sense (Acer Predator PHN16-71)."""
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk
import json, sys, math, colorsys
from pathlib import Path

BASE = "/sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi"
KB = f"{BASE}/four_zoned_kb"
PS = f"{BASE}/predator_sense"
STATE_FILE = Path.home() / ".config" / "linuwu-sense-gui" / "state.json"

MODES = ["Static", "Breathing", "Neon", "Wave", "Shifting", "Zoom", "Meteor", "Twinkling"]
PRESETS = ["ff0000", "ff7f00", "ffff00", "00ff00", "00ffff",
           "0000ff", "8b00ff", "ff00ff", "ffffff", "202020"]

DEFAULT_STATE = {
    "kb_on": False,
    "boot_dim": False,
    "active_mode": "effect",
    "effect": {"mode": 3, "speed": 5, "brightness": 100, "direction": 1, "color": [0, 150, 255]},
    "zone": {"colors": ["ff0000", "00ff00", "0000ff", "ffffff"], "brightness": 100},
    "backlight_timeout": 0,
    "cpu_fan": 0,
    "gpu_fan": 0,
}


def load_state():
    try:
        merged = json.loads(json.dumps(DEFAULT_STATE))
        loaded = json.loads(STATE_FILE.read_text())
        merged["effect"].update(loaded.get("effect", {}))
        merged["zone"].update(loaded.get("zone", {}))
        for k in ("kb_on", "boot_dim", "active_mode", "backlight_timeout", "cpu_fan", "gpu_fan"):
            if k in loaded:
                merged[k] = loaded[k]
        return merged
    except Exception:
        return json.loads(json.dumps(DEFAULT_STATE))


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


def write(path, value):
    with open(path, "w") as f:
        f.write(value)


def read(path, default=""):
    try:
        return open(path).read().strip()
    except Exception:
        return default

def apply_keyboard(state, boot=False):
    dim = boot and state.get("boot_dim", False)
    if not state["kb_on"]:
        write(f"{KB}/four_zone_mode", "0,0,0,1,0,0,0")
        return
    if state["active_mode"] == "zone":
        z = state["zone"]
        bright = 0 if dim else z["brightness"]
        write(f"{KB}/per_zone_mode", f"{','.join(z['colors'])},{bright}")
        return
    e = state["effect"]
    r, g, b = e["color"]
    bright = 0 if dim else e["brightness"]
    if e["mode"] == 0:  # Static: use per_zone_mode with one color on all zones
        hx = "%02x%02x%02x" % (r, g, b)
        write(f"{KB}/per_zone_mode", f"{hx},{hx},{hx},{hx},{bright}")
    else:
        write(f"{KB}/four_zone_mode",
              f"{e['mode']},{e['speed']},{bright},{e['direction']},{r},{g},{b}")

def apply_backlight_timeout(state):
    write(f"{PS}/backlight_timeout", str(state["backlight_timeout"]))


def apply_fans(state):
    write(f"{PS}/fan_speed", f"{state['cpu_fan']},{state['gpu_fan']}")


def apply_all(state):
    apply_keyboard(state, boot=True)
    try:
        apply_backlight_timeout(state)
    except Exception:
        pass
    try:
        apply_fans(state)
    except Exception:
        pass

def set_solid_bg(widget, name, hexcol, extra=""):
    """Force a flat background color onto a widget, bypassing theme gradients."""
    widget.set_name(name)
    provider = getattr(widget, "_bg_provider", None)
    if provider is None:
        provider = Gtk.CssProvider()
        widget._bg_provider = provider
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    provider.load_from_data(
        f"#{name} {{ background-image: none; background-color: #{hexcol}; "
        f"box-shadow: none; border: 1px solid alpha(#000000, 0.25); {extra} }}".encode()
    )


class ColorWheel(Gtk.Box):
    def __init__(self, rgb=(0, 150, 255)):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.on_change = None
        self.h, self.s, self.v = self._rgb_to_hsv(rgb)

        self.area = Gtk.DrawingArea()
        self.area.set_content_width(180)
        self.area.set_content_height(180)
        self.area.set_draw_func(self._draw)

        click = Gtk.GestureClick()
        click.connect("pressed", lambda g, n, x, y: self._pick(x, y))
        self.area.add_controller(click)

        drag = Gtk.GestureDrag()
        drag.connect("drag-update", self._on_drag_update)
        self.area.add_controller(drag)

        self.append(self.area)

        self.value_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.value_scale.set_value(self.v * 100)
        self.value_scale.connect("value-changed", self._on_value_changed)
        self.append(self.value_scale)

        preset_row = Gtk.Box(spacing=6)
        for i, hexcol in enumerate(PRESETS):
            btn = Gtk.Button()
            btn.set_size_request(24, 24)
            set_solid_bg(btn, f"preset-{id(self)}-{i}", hexcol, "border-radius: 5px; min-width:24px; min-height:24px; padding:0;")
            btn.connect("clicked", lambda b, h=hexcol: self._set_hex_and_emit(h))
            preset_row.append(btn)
        self.append(preset_row)

        hex_row = Gtk.Box(spacing=6)
        hex_row.append(Gtk.Label(label="Hex"))
        self.hex_entry = Gtk.Entry()
        self.hex_entry.set_text(self.current_hex())
        self.hex_entry.connect("activate", self._on_hex_entered)
        hex_row.append(self.hex_entry)
        self.append(hex_row)

    @staticmethod
    def _rgb_to_hsv(rgb):
        r, g, b = (c / 255 for c in rgb)
        return colorsys.rgb_to_hsv(r, g, b)

    def get_rgb(self):
        r, g, b = colorsys.hsv_to_rgb(self.h, self.s, self.v)
        return (round(r * 255), round(g * 255), round(b * 255))

    def current_hex(self):
        r, g, b = self.get_rgb()
        return "%02x%02x%02x" % (r, g, b)

    def set_rgb(self, rgb, emit=False):
        self.h, self.s, self.v = self._rgb_to_hsv(rgb)
        self.value_scale.set_value(self.v * 100)
        self.hex_entry.set_text(self.current_hex())
        self.area.queue_draw()
        if emit:
            self._emit()

    def _set_hex_and_emit(self, hexcol):
        self.set_rgb((int(hexcol[0:2], 16), int(hexcol[2:4], 16), int(hexcol[4:6], 16)), emit=True)

    def _emit(self):
        self.hex_entry.set_text(self.current_hex())
        if self.on_change:
            self.on_change(*self.get_rgb())

    def _draw(self, area, cr, w, h):
        cx, cy = w / 2, h / 2
        radius = min(cx, cy) - 4
        for i in range(0, 360, 2):
            a0, a1 = math.radians(i), math.radians(i + 2.5)
            for j in range(1, 11):
                sat = j / 10
                r, g, b = colorsys.hsv_to_rgb(i / 360, sat, 1.0)
                cr.set_source_rgb(r, g, b)
                cr.move_to(cx, cy)
                cr.arc(cx, cy, radius * sat, a0, a1)
                cr.fill()
        mr = self.s * radius
        ma = math.radians(self.h * 360)
        mx, my = cx + mr * math.cos(ma), cy + mr * math.sin(ma)
        cr.set_source_rgb(0, 0, 0)
        cr.set_line_width(2)
        cr.arc(mx, my, 6, 0, 2 * math.pi)
        cr.stroke()
        cr.set_source_rgb(1, 1, 1)
        cr.arc(mx, my, 4, 0, 2 * math.pi)
        cr.stroke()

    def _pick(self, x, y):
        w, h = self.area.get_width(), self.area.get_height()
        cx, cy = w / 2, h / 2
        radius = min(cx, cy) - 4
        dx, dy = x - cx, y - cy
        dist = min(math.hypot(dx, dy), radius)
        ang = math.atan2(dy, dx)
        if ang < 0:
            ang += 2 * math.pi
        self.h, self.s = ang / (2 * math.pi), dist / radius
        self.area.queue_draw()
        self._emit()

    def _on_drag_update(self, gesture, dx, dy):
        ok, x0, y0 = gesture.get_start_point()
        self._pick(x0 + dx, y0 + dy)

    def _on_value_changed(self, scale):
        self.v = scale.get_value() / 100
        self._emit()

    def _on_hex_entered(self, entry):
        t = entry.get_text().strip().lstrip("#")
        if len(t) == 6:
            try:
                self._set_hex_and_emit(t)
            except ValueError:
                pass


class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Predator Control")
        self.set_default_size(460, 640)
        self.state = load_state()
        self._ready = False  # guard against auto-apply firing while widgets are being built

        header = Gtk.HeaderBar()
        self.set_titlebar(header)

        stack = Gtk.Stack()
        header.set_title_widget(Gtk.StackSwitcher(stack=stack))

        stack.add_titled(self.build_keyboard_page(), "keyboard", "Keyboard")
        stack.add_titled(self.build_fan_page(), "fans", "Fans")
        self.set_child(stack)
        self._ready = True

    def build_keyboard_page(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        for m in ("margin_top", "margin_bottom", "margin_start", "margin_end"):
            getattr(outer, f"set_{m}")(18)

        row = Gtk.Box(spacing=8)
        row.append(Gtk.Label(label="Backlight", xalign=0, hexpand=True))
        self.kb_switch = Gtk.Switch(active=self.state["kb_on"])
        self.kb_switch.connect("state-set", self.on_master_toggle)
        row.append(self.kb_switch)
        outer.append(row)
        dim_row = Gtk.Box(spacing=8)
        dim_row.append(Gtk.Label(label="Start at 0 brightness after restart", xalign=0, hexpand=True))
        self.dim_switch = Gtk.Switch(active=self.state.get("boot_dim", False))
        self.dim_switch.connect("state-set", self.on_dim_toggle)
        dim_row.append(self.dim_switch)
        outer.append(dim_row)
        outer.append(Gtk.Separator())

        sub = Gtk.Notebook()
        sub.append_page(self.build_effect_tab(), Gtk.Label(label="Effect"))
        sub.append_page(self.build_zone_tab(), Gtk.Label(label="Per-zone"))
        sub.set_current_page(0 if self.state["active_mode"] == "effect" else 1)
        outer.append(sub)

        outer.append(Gtk.Separator())
        outer.append(Gtk.Label(label="Auto-off timeout (fixed hardware feature)", xalign=0))
        self.timeout_dropdown = Gtk.DropDown.new_from_strings(
            ["Never", "Auto-off after 30s idle"])
        self.timeout_dropdown.set_selected(self.state["backlight_timeout"])
        self.timeout_dropdown.connect("notify::selected", self.on_timeout_changed)
        outer.append(self.timeout_dropdown)
        note = Gtk.Label(
            label="The driver only supports a fixed 30-second idle timeout; there's no custom duration.",
            wrap=True)
        note.add_css_class("dim-label")
        outer.append(note)
        return outer

    def build_effect_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(12)

        box.append(Gtk.Label(label="Mode", xalign=0))
        self.mode_dropdown = Gtk.DropDown.new_from_strings(MODES)
        self.mode_dropdown.set_selected(self.state["effect"]["mode"])
        self.mode_dropdown.connect("notify::selected", self.on_effect_changed)
        box.append(self.mode_dropdown)

        box.append(Gtk.Label(label="Speed", xalign=0))
        self.speed_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 9, 1)
        self.speed_scale.set_value(self.state["effect"]["speed"])
        self.speed_scale.connect("value-changed", self.on_effect_changed)
        box.append(self.speed_scale)

        box.append(Gtk.Label(label="Brightness", xalign=0))
        self.effect_bright_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.effect_bright_scale.set_value(self.state["effect"]["brightness"])
        self.effect_bright_scale.connect("value-changed", self.on_effect_changed)
        box.append(self.effect_bright_scale)

        dir_row = Gtk.Box(spacing=8)
        dir_row.append(Gtk.Label(label="Direction", xalign=0, hexpand=True))
        self.dir_toggle = Gtk.ToggleButton(
            label="Left → Right" if self.state["effect"]["direction"] == 2 else "Right → Left")
        self.dir_toggle.set_active(self.state["effect"]["direction"] == 2)
        self.dir_toggle.connect("toggled", self.on_direction_toggled)
        dir_row.append(self.dir_toggle)
        box.append(dir_row)

        box.append(Gtk.Label(label="Color", xalign=0))
        self.effect_wheel = ColorWheel(tuple(self.state["effect"]["color"]))
        self.effect_wheel.on_change = self.on_effect_color_changed
        box.append(self.effect_wheel)
        return box

    def build_zone_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(12)

        box.append(Gtk.Label(label="Select a zone, then pick its color", xalign=0))
        self.zone_selected = 0
        self.zone_swatches = []
        swatch_row = Gtk.Box(spacing=8)
        for i in range(4):
            btn = Gtk.Button(label=f"Zone {i + 1}")
            btn.set_size_request(70, 36)
            set_solid_bg(btn, f"zone-swatch-{i}", self.state["zone"]["colors"][i], "border-radius: 6px;")
            btn.connect("clicked", lambda b, idx=i: self.on_select_zone(idx))
            swatch_row.append(btn)
            self.zone_swatches.append(btn)
        box.append(swatch_row)

        self.zone_wheel = ColorWheel(self._hex_to_rgb(self.state["zone"]["colors"][0]))
        self.zone_wheel.on_change = self.on_zone_color_changed
        box.append(self.zone_wheel)

        box.append(Gtk.Label(label="Overall zone brightness", xalign=0))
        self.zone_bright_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.zone_bright_scale.set_value(self.state["zone"]["brightness"])
        self.zone_bright_scale.connect("value-changed", self.on_zone_brightness_changed)
        box.append(self.zone_bright_scale)
        return box

    @staticmethod
    def _hex_to_rgb(h):
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    def on_select_zone(self, idx):
        self.zone_selected = idx
        self.zone_wheel.set_rgb(self._hex_to_rgb(self.state["zone"]["colors"][idx]))

    def on_master_toggle(self, switch, active):
        self.state["kb_on"] = active
        apply_keyboard(self.state)
        save_state(self.state)
        return False

    def on_dim_toggle(self, switch, active):
        self.state["boot_dim"] = active
        save_state(self.state)
        return False

    def _commit_effect(self):
        if not self._ready:
            return
        r, g, b = self.effect_wheel.get_rgb()
        self.state["effect"] = {
            "mode": self.mode_dropdown.get_selected(),
            "speed": int(self.speed_scale.get_value()),
            "brightness": int(self.effect_bright_scale.get_value()),
            "direction": 2 if self.dir_toggle.get_active() else 1,
            "color": [r, g, b],
        }
        self.state["active_mode"] = "effect"
        self.state["kb_on"] = True
        self.kb_switch.set_active(True)
        apply_keyboard(self.state)
        save_state(self.state)

    def on_effect_changed(self, *_args):
        self._commit_effect()

    def on_direction_toggled(self, btn):
        btn.set_label("Left → Right" if btn.get_active() else "Right → Left")
        self._commit_effect()

    def on_effect_color_changed(self, r, g, b):
        self._commit_effect()

    def on_zone_color_changed(self, r, g, b):
        if not self._ready:
            return
        hexcol = "%02x%02x%02x" % (r, g, b)
        self.state["zone"]["colors"][self.zone_selected] = hexcol
        set_solid_bg(self.zone_swatches[self.zone_selected], f"zone-swatch-{self.zone_selected}",
                     hexcol, "border-radius: 6px;")
        self.state["active_mode"] = "zone"
        self.state["kb_on"] = True
        self.kb_switch.set_active(True)
        apply_keyboard(self.state)
        save_state(self.state)

    def on_zone_brightness_changed(self, scale):
        if not self._ready:
            return
        self.state["zone"]["brightness"] = int(scale.get_value())
        self.state["active_mode"] = "zone"
        self.state["kb_on"] = True
        self.kb_switch.set_active(True)
        apply_keyboard(self.state)
        save_state(self.state)

    def on_timeout_changed(self, dropdown, _pspec):
        if not self._ready:
            return
        self.state["backlight_timeout"] = dropdown.get_selected()
        apply_backlight_timeout(self.state)
        save_state(self.state)

    def build_fan_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for m in ("margin_top", "margin_bottom", "margin_start", "margin_end"):
            getattr(box, f"set_{m}")(18)

        cur = read(f"{PS}/fan_speed", "0,0")
        try:
            cpu_cur, gpu_cur = (int(x) for x in cur.split(","))
        except Exception:
            cpu_cur, gpu_cur = 0, 0

        box.append(Gtk.Label(label="CPU fan (0 = auto)", xalign=0))
        self.cpu_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.cpu_scale.set_value(cpu_cur)
        self.cpu_scale.connect("value-changed", self.on_fan_changed)
        box.append(self.cpu_scale)

        box.append(Gtk.Label(label="GPU fan (0 = auto)", xalign=0))
        self.gpu_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.gpu_scale.set_value(gpu_cur)
        self.gpu_scale.connect("value-changed", self.on_fan_changed)
        box.append(self.gpu_scale)

        auto_btn = Gtk.Button(label="Auto")
        auto_btn.connect("clicked", self.on_fan_auto)
        box.append(auto_btn)

        note = Gtk.Label(
            label="Values are a target %, not RPM. 0 hands control back to firmware.", wrap=True)
        note.add_css_class("dim-label")
        box.append(note)
        return box

    def on_fan_changed(self, _scale):
        if not self._ready:
            return
        self.state["cpu_fan"] = int(self.cpu_scale.get_value())
        self.state["gpu_fan"] = int(self.gpu_scale.get_value())
        apply_fans(self.state)
        save_state(self.state)

    def on_fan_auto(self, _btn):
        self.cpu_scale.set_value(0)
        self.gpu_scale.set_value(0)


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="dev.linuwusensegui.Control")

    def do_activate(self):
        Window(self).present()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--apply-saved":
        apply_all(load_state())
        return
    App().run(None)


if __name__ == "__main__":
    main()
