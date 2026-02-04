from tkinter import Canvas, Toplevel, font as tkfont


class SplashScreen:
    """Animated splash: types out 'Geni' then slides 'mail' out from the i."""

    TRANSPARENT_KEY = "#010101"

    def __init__(self, root, on_complete):
        self.root = root
        self.on_complete = on_complete

        self.win = Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-transparentcolor", self.TRANSPARENT_KEY)
        except Exception:
            pass

        w, h = 620, 180
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        self.canvas = Canvas(
            self.win,
            width=w,
            height=h,
            bg=self.TRANSPARENT_KEY,
            highlightthickness=0,
        )
        self.canvas.pack()

        self._font_geni = tkfont.Font(family="Segoe UI", size=52, weight="bold")
        self._font_mail = tkfont.Font(family="Segoe UI", size=38, weight="bold")

        geni_width = self._font_geni.measure("Geni")
        mail_width = self._font_mail.measure("mail")
        total_width = geni_width + mail_width + 4
        self._base_x = (w - total_width) // 2
        self._cy = h // 2

        self._letter_x = []
        x = self._base_x
        for ch in "Geni":
            self._letter_x.append(x)
            x += self._font_geni.measure(ch)

        i_right_edge = x
        self._mail_origin_x = i_right_edge
        self._mail_final_x = i_right_edge + 4

        ascent_geni = self._font_geni.metrics()["ascent"]
        ascent_mail = self._font_mail.metrics()["ascent"]
        self._mail_y_offset = (ascent_geni - ascent_mail) * 0.45

        self._i_x = self._letter_x[-1]
        self._i_right = i_right_edge

        self._shadow_deep = "#003300"
        self._shadow_mid = "#005500"
        self._color_main = "#00dd44"
        self._color_shine = "#55ffaa"

        self._typed = 0
        self._mail_items = []
        self._mail_created = False
        self._i_cover_items = []

        self.win.after(300, self._type_next)

    def _draw_3d_text(self, x, y, text, font):
        self.canvas.create_text(x + 3, y + 3, text=text, font=font, fill=self._shadow_deep, anchor="w")
        self.canvas.create_text(x + 1, y + 1, text=text, font=font, fill=self._shadow_mid, anchor="w")
        self.canvas.create_text(x, y, text=text, font=font, fill=self._color_main, anchor="w")
        self.canvas.create_text(x - 1, y - 1, text=text, font=font, fill=self._color_shine, anchor="w")

    def _draw_3d_text_items(self, x, y, text, font):
        items = []
        items.append(
            self.canvas.create_text(x + 3, y + 3, text=text, font=font, fill=self._shadow_deep, anchor="w")
        )
        items.append(self.canvas.create_text(x + 1, y + 1, text=text, font=font, fill=self._shadow_mid, anchor="w"))
        items.append(self.canvas.create_text(x, y, text=text, font=font, fill=self._color_main, anchor="w"))
        items.append(self.canvas.create_text(x - 1, y - 1, text=text, font=font, fill=self._color_shine, anchor="w"))
        return items

    def _type_next(self):
        letters = "Geni"
        if self._typed < len(letters):
            x = self._letter_x[self._typed]
            self._draw_3d_text(x, self._cy, letters[self._typed], self._font_geni)
            self._typed += 1
            self.win.after(150, self._type_next)
        else:
            self.win.after(250, lambda: self._slide_mail(0))

    def _slide_mail(self, frame):
        total_frames = 14
        frame_delay = 50

        t = frame / total_frames
        t = t * (2 - t)

        cur_x = self._mail_origin_x + (self._mail_final_x - self._mail_origin_x) * t
        y = self._cy + self._mail_y_offset

        if not self._mail_created:
            self._mail_items = self._draw_3d_text_items(cur_x, y, "mail", self._font_mail)
            self._mail_created = True
            self._mail_offsets = [(3, 3), (1, 1), (0, 0), (-1, -1)]
        else:
            for item, (ox, oy) in zip(self._mail_items, self._mail_offsets):
                self.canvas.coords(item, cur_x + ox, y + oy)

        for item in self._i_cover_items:
            self.canvas.delete(item)
        self._i_cover_items.clear()

        pad = 6
        self._i_cover_items.append(
            self.canvas.create_rectangle(
                self._i_x - pad,
                self._cy - 50,
                self._i_right,
                self._cy + 50,
                fill=self.TRANSPARENT_KEY,
                outline="",
            )
        )
        for ox, oy, color in [
            (3, 3, self._shadow_deep),
            (1, 1, self._shadow_mid),
            (0, 0, self._color_main),
            (-1, -1, self._color_shine),
        ]:
            self._i_cover_items.append(
                self.canvas.create_text(
                    self._i_x + ox,
                    self._cy + oy,
                    text="i",
                    font=self._font_geni,
                    fill=color,
                    anchor="w",
                )
            )

        if frame < total_frames:
            self.win.after(frame_delay, lambda: self._slide_mail(frame + 1))
        else:
            for item in self._i_cover_items:
                self.canvas.delete(item)
            self._i_cover_items.clear()
            self._draw_3d_text(self._i_x, self._cy, "i", self._font_geni)
            self.win.after(1100, self._finish)

    def _finish(self):
        try:
            self.win.destroy()
        except Exception:
            pass
        self.on_complete()
