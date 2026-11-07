"""Responsive desktop preview. Rendering never writes configuration."""

from dataclasses import replace

from .render import draw_window, draw_text, fill, derived, lines


def draw_preview(self, widget, cr):
    width = widget.get_allocated_width()
    height = widget.get_allocated_height()
    section = self.section.get_active_text()
    selected_only = self.preview_mode.get_active() == 1

    def rect(x, y, w, h, bg):
        fill(cr, x, y, w, h, bg)

    def text(x, y, value, fg, size=12, section="TrayStyle"):
        font = self.current(section, ("Font",)) or "Sans-12"
        draw_text(cr, x, y - size - 2, value, fg, font)

    def v(s, *path, fallback=None):
        return self.current(s, tuple(path)) or fallback

    def relief(x, y, w, h, bg, raised=True):
        rect(x, y, w, h, bg)
        up, down = derived(bg.split(":")[0].split(";")[0], True), derived(
            bg.split(":")[0].split(";")[0], False
        )
        if not raised:
            up, down = down, up
        lines(cr, [(x + w - 1, y, x, y), (x, y, x, y + h - 1)], up)
        lines(
            cr,
            [
                (x + w - 1, y, x + w - 1, y + h - 1),
                (x + w - 1, y + h - 1, x, y + h - 1),
            ],
            down,
        )

    def frame(section, x, y, w, h, bg, raised=True):
        if v(section, "@decorations", fallback="flat") == "motif":
            relief(x, y, w, h, bg, raised)
        else:
            rect(x, y, w, h, bg)

    def window(x, y, w, h, active):
        draw_window(
            cr,
            x,
            y,
            w,
            h,
            active,
            self.effective_values(),
            replace(
                self.buttons,
                decorations=self.current("WindowStyle", ("@decorations",))
                or self.buttons.decorations,
            ),
            maximized=self.preview_maximized.get_active(),
        )

    def tray(x, y, w, h):
        bg = v("TrayStyle", "Background", fallback="#35383B")
        fg = v("TrayStyle", "Foreground", fallback="#E5E1D8")
        frame("TrayStyle", x, y, w, h, bg)
        start = self.start_attributes or {}
        text(
            x + 10,
            y + 23,
            self.start_pending.get("label", start.get("label", "Menu")) or "Menu",
            fg,
        )
        for i, name in enumerate(["Terminal", "Firefox"]):
            active = i == 0
            bx = x + 62 + i * 90
            bbg = (
                v("TaskListStyle", "Active", "Background", fallback="#D09A52")
                if active
                else v("TaskListStyle", "Background", fallback="#35383B")
            )
            bfg = (
                v("TaskListStyle", "Active", "Foreground", fallback="#202124")
                if active
                else v("TaskListStyle", "Foreground", fallback="#E5E1D8")
            )
            frame("TaskListStyle", bx, y + 5, 84, 27, bbg, not active)
            text(bx + 5, y + 23, name, bfg, 11, "TaskListStyle")

    def menu(x, y):
        bg = v("MenuStyle", "Background", fallback="#35383B")
        fg = v("MenuStyle", "Foreground", fallback="#E5E1D8")
        abg = v("MenuStyle", "Active", "Background", fallback="#D09A52")
        afg = v("MenuStyle", "Active", "Foreground", fallback="#202124")
        frame("MenuStyle", x, y, 152, 111, bg)
        for i, label in enumerate(["Applications", "Terminal", "Settings", "Exit"]):
            if i == 1:
                rect(x + 5, y + 7 + i * 25, 142, 24, abg)
            text(x + 12, y + 24 + i * 25, label, afg if i == 1 else fg, 12, "MenuStyle")

    def pager(x, y):
        bg = v("PagerStyle", "Background", fallback="#35383B")
        fg = v("PagerStyle", "Text", fallback="#E5E1D8")
        abg = v("PagerStyle", "Active", "Background", fallback="#202124")
        rect(x, y, 156, 47, bg)
        for i in range(4):
            relief(x + 4 + i * 38, y + 6, 35, 35, abg if i == 0 else bg, i != 0)
            text(x + 17 + i * 38, y + 29, str(i + 1), fg, 11, "PagerStyle")

    cr.save()
    cr.rectangle(0, 0, width, height)
    cr.clip()
    rect(0, 0, width, height, "#292B2E")
    scale = min(width / 470, height / 400)
    cr.save()
    cr.translate((width - 470 * scale) / 2, (height - 400 * scale) / 2)
    cr.scale(scale, scale)
    if not selected_only or section == "WindowStyle":
        window(20, 18, 355, 156, True)
        window(85, 185, 355, 116, False)
    if not selected_only or section == "MenuStyle":
        menu(285 if not selected_only else 155, 80 if not selected_only else 35)
    if not selected_only or section == "PopupStyle":
        bg = v("PopupStyle", "Background", fallback="#B8B6AF")
        fg = v("PopupStyle", "Foreground", fallback="#202124")
        relief(24, 313 if not selected_only else 45, 160, 34, bg)
        text(
            34, 335 if not selected_only else 67, "Sample tooltip", fg, 12, "PopupStyle"
        )
    if not selected_only or section in ("TrayStyle", "TaskListStyle", "Start Button"):
        tray(12, 357 if not selected_only else 50, 446, 38)
    if not selected_only or section == "PagerStyle":
        pager(296 if not selected_only else 150, 305 if not selected_only else 50)
    cr.restore()
    cr.restore()
    return False
