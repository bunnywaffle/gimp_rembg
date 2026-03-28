#!/usr/bin/env python3
"""GIMP 3 plugin for AI background removal using rembg."""

import gi

gi.require_version("Gimp", "3.0")
gi.require_version("Gegl", "0.4")
gi.require_version("Gtk", "3.0")
from gi.repository import Gimp, Gegl, GLib, Gio, Gtk
import sys
import os
import subprocess
import platform
import shutil

Gegl.init(None)

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
WORKER_SCRIPT = os.path.join(PLUGIN_DIR, "rembg_worker.py")

if platform.system() == "Windows":
    VENV_DIR = os.path.join(PLUGIN_DIR, "venv")
    VENV_PYTHON = os.path.join(VENV_DIR, "Scripts", "python.exe")
    VENV_PIP = os.path.join(VENV_DIR, "Scripts", "pip.exe")
else:
    VENV_DIR = os.path.join(PLUGIN_DIR, "venv")
    VENV_PYTHON = os.path.join(VENV_DIR, "bin", "python")
    VENV_PIP = os.path.join(VENV_DIR, "bin", "pip")

SYSTEM_PYTHON_PATHS = [
    "/usr/bin/python3",
    "/usr/local/bin/python3",
    "/usr/bin/python",
    os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Programs",
        "Python",
        "Python313",
        "python.exe",
    ),
    os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Programs",
        "Python",
        "Python312",
        "python.exe",
    ),
    os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Programs",
        "Python",
        "Python311",
        "python.exe",
    ),
    os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Programs",
        "Python",
        "Python310",
        "python.exe",
    ),
]

MODELS = [
    ("u2net", "General - Works for most images"),
    ("u2net_human_seg", "People - Portraits and selfies"),
    ("u2net_cloth_seg", "Clothing - Fashion and apparel"),
    ("isnet-general-use", "Objects - Products and items"),
    ("isnet-anime", "Art - Anime and illustrations"),
    ("silueta", "Silhouette - Clean object outlines"),
    ("birefnet-general", "Complex - Busy backgrounds"),
    ("birefnet-dis", "Detailed - Fine edges and hair"),
    ("birefnet-hrsod", "High-res - Large detailed images"),
    ("birefnet-cod", "Hidden - Blended or camouflaged"),
]


def find_python():
    if os.path.isfile(VENV_PYTHON):
        try:
            r = subprocess.run(
                [VENV_PYTHON, "-c", "import rembg"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if r.returncode == 0:
                return VENV_PYTHON
        except Exception:
            pass
    for p in SYSTEM_PYTHON_PATHS:
        if os.path.exists(p):
            try:
                r = subprocess.run(
                    [p, "-c", "import rembg"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if r.returncode == 0:
                    return p
            except Exception:
                pass
    try:
        r = subprocess.run(
            [sys.executable, "-c", "import rembg"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            return sys.executable
    except Exception:
        pass
    return None


def check_rembg():
    return find_python() is not None


def run_setup_internal(progress, status):
    def update(text, frac=None):
        if status:
            status.set_text(text)
        if progress and frac is not None:
            progress.set_fraction(frac)
        while Gtk.events_pending():
            Gtk.main_iteration()

    if os.path.exists(VENV_DIR):
        update("Removing old environment...", 0.05)
        shutil.rmtree(VENV_DIR)

    update("Creating isolated environment...", 0.1)
    r = subprocess.run(
        [sys.executable, "-m", "venv", VENV_DIR], capture_output=True, text=True
    )
    if r.returncode != 0:
        return False, f"venv create failed:\n{r.stderr}"

    update("Upgrading pip...", 0.2)
    subprocess.run(
        [VENV_PIP, "install", "--upgrade", "pip"], capture_output=True, text=True
    )

    update("Installing rembg (may take a few minutes)...", 0.3)
    r = subprocess.run(
        [VENV_PIP, "install", "pillow", "onnxruntime", "rembg"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return False, f"pip failed:\n{r.stderr}\n{r.stdout}"

    update("Verifying...", 0.9)
    r = subprocess.run(
        [VENV_PYTHON, "-c", "import rembg; print(rembg.__version__)"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return False, f"verify failed:\n{r.stderr}"
    return True, r.stdout.strip()


def show_model_dialog(title):
    """Show a dialog with model dropdown. Returns model_id or None if cancelled."""
    dlg = Gtk.Dialog(title=title)
    dlg.set_default_size(350, 100)
    dlg.set_resizable(False)

    box = dlg.get_content_area()

    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    row.set_margin_start(15)
    row.set_margin_end(15)
    row.set_margin_top(15)
    row.set_margin_bottom(10)

    lbl = Gtk.Label(label="Model:")
    row.pack_start(lbl, False, False, 0)

    combo = Gtk.ComboBoxText()
    for mid, mlabel in MODELS:
        combo.append(mid, mlabel)
    combo.set_active(0)
    row.pack_start(combo, True, True, 0)

    box.pack_start(row, False, False, 0)

    dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
    dlg.add_button("Run", Gtk.ResponseType.OK)

    dlg.show_all()
    resp = dlg.run()
    model = combo.get_active_id()
    dlg.destroy()

    if resp == Gtk.ResponseType.OK and model:
        return model
    return None


class RembgPlugin(Gimp.PlugIn):
    def do_query_procedures(self):
        return ["rembg-setup", "rembg-remove-bg", "rembg-remove-bg-mask"]

    def do_create_procedure(self, name):
        proc = Gimp.ImageProcedure.new(
            self, name, Gimp.PDBProcType.PLUGIN, self.run, None
        )
        proc.set_image_types("*")
        proc.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)

        if name == "rembg-setup":
            proc.set_menu_label("Setup...")
            proc.set_documentation("Setup rembg", "Install rembg AI engine", name)
        elif name == "rembg-remove-bg":
            proc.set_menu_label("Remove Background (Destructive)...")
            proc.set_documentation(
                "Remove background", "Removes background permanently", name
            )
        else:
            proc.set_menu_label("Remove Background (Mask)...")
            proc.set_documentation("Remove background", "Creates a layer mask", name)

        proc.set_attribution("GIMP Rembg", "GIMP Rembg", "2025")
        proc.add_menu_path("<Image>/Rembg/")
        return proc

    def run(self, procedure, run_mode, image, drawables, config, data):
        name = procedure.get_name()
        if name == "rembg-setup":
            return self._do_setup(procedure)
        elif name == "rembg-remove-bg":
            return self._do_remove(procedure, image, drawables, destructive=True)
        else:
            return self._do_remove(procedure, image, drawables, destructive=False)

    # ─── Setup ────────────────────────────────────────────────

    def _do_setup(self, procedure):
        if check_rembg():
            dlg = Gtk.MessageDialog(
                None,
                0,
                Gtk.MessageType.QUESTION,
                Gtk.ButtonsType.YES_NO,
                "rembg is already installed.\n\nReinstall?",
            )
            dlg.set_title("Rembg Setup")
            resp = dlg.run()
            dlg.destroy()
            if resp != Gtk.ResponseType.YES:
                return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, None)

        win = Gtk.Dialog(title="Rembg Setup")
        win.set_default_size(420, 180)
        win.set_resizable(False)
        box = win.get_content_area()

        label = Gtk.Label(
            label="Click Start to install rembg.\nDownloads ~500MB of AI models."
        )
        label.set_margin_top(12)
        box.pack_start(label, False, False, 0)

        progress = Gtk.ProgressBar()
        progress.set_margin_start(20)
        progress.set_margin_end(20)
        box.pack_start(progress, False, False, 6)

        status = Gtk.Label(label="Ready")
        box.pack_start(status, False, False, 4)

        btn_box = Gtk.Box(spacing=10)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_bottom(12)
        start_btn = Gtk.Button(label="Start Setup")
        close_btn = Gtk.Button(label="Close")
        btn_box.pack_start(start_btn, False, False, 0)
        btn_box.pack_start(close_btn, False, False, 0)
        box.pack_start(btn_box, False, False, 0)

        win.show_all()

        def on_start(btn):
            start_btn.set_sensitive(False)
            ok, msg = run_setup_internal(progress, status)
            if ok:
                label.set_text(
                    f"rembg {msg} installed!\nRestart GIMP to use Remove Background."
                )
                status.set_text("Setup complete.")
                progress.set_fraction(1.0)
            else:
                label.set_text("Setup failed!")
                status.set_text(msg[:300])
                progress.set_fraction(0)
            start_btn.set_sensitive(True)

        start_btn.connect("clicked", on_start)
        close_btn.connect("clicked", lambda b: win.destroy())
        win.connect("destroy", Gtk.main_quit)
        Gtk.main()

        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, None)

    # ─── Remove Background ────────────────────────────────────

    def _do_remove(self, procedure, image, drawables, destructive=True):
        if not drawables:
            return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, None)

        python_exe = find_python()
        if not python_exe:
            Gimp.message(
                "rembg not found!\n\n"
                "Run setup first: Rembg > Setup..."
            )
            return procedure.new_return_values(
                Gimp.PDBStatusType.EXECUTION_ERROR,
                GLib.Error(message="rembg not installed"),
            )

        # Show model picker dialog
        title = "Remove Background" + (" (Destructive)" if destructive else " (Mask)")
        model = show_model_dialog(title)
        if model is None:
            return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, None)

        layer = drawables[0]
        image.undo_group_start()

        temp_in = Gimp.temp_file("png")
        temp_in_path = temp_in.get_path()
        temp_out_path = temp_in_path.replace(".png", "_out.png")

        try:
            success, x_orig, y_orig = layer.get_offsets()

            temp_image = Gimp.Image.new(
                layer.get_width(), layer.get_height(), image.get_base_type()
            )
            layer_copy = Gimp.Layer.new_from_drawable(layer, temp_image)
            temp_image.insert_layer(layer_copy, None, 0)
            layer_copy.set_offsets(0, 0)
            Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, temp_image, temp_in, None)
            temp_image.delete()

            Gimp.progress_init(f"Removing background with {model}...")
            Gimp.progress_update(0.1)

            r = subprocess.run(
                [python_exe, WORKER_SCRIPT, temp_in_path, temp_out_path, model],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if r.returncode != 0:
                raise Exception(f"Worker failed: {r.stderr or 'Unknown error'}")

            if not os.path.exists(temp_out_path):
                raise Exception("AI did not produce output file")

            Gimp.progress_update(0.8)

            res_gio = Gio.File.new_for_path(temp_out_path)
            result_layer = Gimp.file_load_layer(
                Gimp.RunMode.NONINTERACTIVE, image, res_gio
            )

            image.insert_layer(result_layer, layer.get_parent(), 0)
            result_layer.set_offsets(x_orig, y_orig)

            mask = layer.create_mask(Gimp.AddMaskType.BLACK)
            layer.add_mask(mask)

            image.select_item(Gimp.ChannelOps.REPLACE, result_layer)
            old_fg = Gimp.context_get_foreground()
            Gimp.context_set_foreground(Gegl.Color.new("white"))
            mask.edit_fill(Gimp.FillType.FOREGROUND)
            Gimp.context_set_foreground(old_fg)

            if destructive:
                layer.remove_mask(Gimp.MaskApplyMode.APPLY)

            Gimp.Selection.none(image)
            image.remove_layer(result_layer)

            layer.set_color_tag(Gimp.ColorTag.RED)
            layer.set_visible(True)
            image.set_selected_layers([layer])

        except Exception as e:
            image.undo_group_end()
            return procedure.new_return_values(
                Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error(message=str(e))
            )
        finally:
            for p in [temp_in_path, temp_out_path]:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass

        image.undo_group_end()
        Gimp.progress_update(1.0)
        Gimp.displays_flush()
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, None)


if __name__ == "__main__":
    Gimp.main(RembgPlugin.__gtype__, sys.argv)
