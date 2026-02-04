import tkinter as tk

from genimail.infra.config_store import Config
from genimail.paths import PDF_DIR
from pdf_viewer import PdfViewerFrame


def main():
    config = Config()
    root = tk.Tk()
    root.title("GENImail Takeoff Tool")
    geometry = config.get("takeoff_window_geometry", "1280x860")
    root.geometry(geometry)
    root.minsize(980, 620)

    viewer = PdfViewerFrame(
        root,
        config_get=config.get,
        config_set=config.set,
        initial_dir=PDF_DIR,
        bg="#ffffff",
        accent="#1f6feb",
    )
    viewer.pack(fill=tk.BOTH, expand=True)

    def on_close():
        config.set("takeoff_window_geometry", root.geometry())
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
