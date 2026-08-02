import os
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.image import Image as KivyImage
from kivy.core.window import Window
from kivy.metrics import dp

from translator_engine import (
    run_phase1, run_phase2, create_final_zip,
    convert_to_images, get_page_paths
)

Window.clearcolor = (0.07, 0.07, 0.09, 1)

# Dynamic Storage Root
if os.path.exists("/storage/emulated/0"):
    STORAGE_ROOT = "/storage/emulated/0"
elif os.path.exists("/sdcard"):
    STORAGE_ROOT = "/sdcard"
else:
    STORAGE_ROOT = os.path.expanduser("~")

WORK_DIR = "workspace"


def request_android_permissions():
    """Requests basic runtime permissions on startup."""
    try:
        from android.permissions import request_permissions, Permission
        request_permissions([
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE,
            Permission.READ_MEDIA_IMAGES
        ])
    except Exception as e:
        print("Runtime permissions skipped:", e)


def has_all_files_access():
    """Checks if All Files Access is granted on Android 11+."""
    try:
        from jnius import autoclass
        Environment = autoclass('android.os.Environment')
        if hasattr(Environment, 'isExternalStorageManager'):
            return bool(Environment.isExternalStorageManager())
        return True
    except Exception:
        return True


def request_all_files_access():
    """Opens exact system toggle page for All Files Access."""
    try:
        from jnius import autoclass
        Intent = autoclass('android.content.Intent')
        Settings = autoclass('android.provider.Settings')
        Uri = autoclass('android.net.Uri')
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        
        activity = PythonActivity.mActivity
        intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
        intent.setData(Uri.parse("package:" + activity.getPackageName()))
        activity.startActivity(intent)
    except Exception:
        # Fallback to general manage storage settings if specific package fails
        try:
            from jnius import autoclass
            Intent = autoclass('android.content.Intent')
            Settings = autoclass('android.provider.Settings')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
            intent = Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION)
            activity.startActivity(intent)
        except Exception as e:
            print("Could not open Storage Settings:", e)


def ext_filters(*exts):
    patterns = []
    for e in exts:
        patterns.append(f"*.{e.lower()}")
        patterns.append(f"*.{e.upper()}")
    return patterns


def make_button(text, color, callback=None, height=50):
    btn = Button(
        text=text, size_hint_y=None, height=dp(height),
        background_color=color, background_normal=''
    )
    if callback:
        btn.bind(on_release=callback)
    return btn


# ============================================================
# File Picker Popup
# ============================================================
class FilePickerPopup(Popup):
    def __init__(self, on_select, filters=None, **kwargs):
        super().__init__(**kwargs)
        self.title = "Select Manga File (PDF / ZIP / Images)"
        self.size_hint = (0.95, 0.95)
        self.on_select_callback = on_select

        layout = BoxLayout(orientation='vertical', spacing=8, padding=8)

        start_path = STORAGE_ROOT if os.path.exists(STORAGE_ROOT) else os.path.expanduser("~")
        self.chooser = FileChooserListView(
            path=start_path,
            filters=filters or ext_filters('pdf', 'zip', 'jpg', 'jpeg', 'png', 'webp'),
            dirselect=False
        )
        layout.add_widget(self.chooser)

        self.path_label = Label(
            text="No file selected", size_hint_y=None, height=dp(30),
            color=(0.7, 0.7, 0.7, 1), font_size='12sp'
        )
        self.chooser.bind(selection=lambda inst, sel: setattr(self.path_label, 'text', os.path.basename(sel[0]) if sel else "No file selected"))
        layout.add_widget(self.path_label)

        btn_row = BoxLayout(size_hint_y=None, height=dp(50), spacing=8)
        select_btn = make_button("Select", (0.2, 0.6, 0.3, 1), self.confirm_selection)
        cancel_btn = make_button("Cancel", (0.6, 0.2, 0.2, 1), lambda x: self.dismiss())
        btn_row.add_widget(select_btn)
        btn_row.add_widget(cancel_btn)
        layout.add_widget(btn_row)

        self.content = layout

    def confirm_selection(self, instance):
        if self.chooser.selection:
            selected_path = self.chooser.selection[0]
            self.dismiss()
            self.on_select_callback(selected_path)


# ============================================================
# Home Screen
# ============================================================
class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=25, spacing=15)
        self.add_widget(self.layout)

    def on_pre_enter(self):
        self.rebuild()

    def rebuild(self):
        self.layout.clear_widgets()

        title = Label(
            text="[b]Manga & Novel Subber Pro[/b]",
            markup=True, font_size='22sp', size_hint_y=None, height=dp(50),
            color=(0.7, 0.5, 1, 1)
        )
        self.layout.add_widget(title)

        if not has_all_files_access():
            self.layout.add_widget(Label(
                text="[color=ff9966]PDF aur ZIP dikhne ke liye All Files Access zaroori hai.[/color]\nNeeche button dabayein aur switch ko ON karein:",
                markup=True, font_size='13sp', size_hint_y=None, height=dp(50),
                halign='center'
            ))
            self.layout.add_widget(make_button(
                "GRANT ALL FILES ACCESS", (0.8, 0.4, 0.1, 1),
                self.grant_access, height=60
            ))
            return

        self.layout.add_widget(Label(
            text="Ek mode choose karein:", font_size='14sp',
            size_hint_y=None, height=dp(30), color=(0.8, 0.8, 0.8, 1)
        ))

        btn_old = make_button(
            "Old Mode (Automatic)", (0.4, 0.2, 0.8, 1),
            lambda x: self.goto('old_mode'), height=60
        )
        btn_manual = make_button(
            "Manual Mode (Bubble Select)", (0.1, 0.6, 0.4, 1),
            lambda x: self.goto('manual_mode'), height=60
        )
        self.layout.add_widget(btn_old)
        self.layout.add_widget(btn_manual)
        self.layout.add_widget(Label())

    def grant_access(self, instance):
        request_all_files_access()

    def goto(self, screen_name):
        self.manager.transition = SlideTransition(direction='left')
        self.manager.current = screen_name


# ============================================================
# Old Mode Screen
# ============================================================
class OldModeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_file = ""
        self.selected_txt = ""

        outer = BoxLayout(orientation='vertical')
        outer.add_widget(self.build_topbar("Old Mode (Automatic)"))

        scroll = ScrollView(size_hint=(1, 1))
        layout = BoxLayout(orientation='vertical', padding=15, spacing=12, size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))

        layout.add_widget(Label(
            text="Step 1: Manga file (PDF/ZIP/JPG) select karein",
            font_size='14sp', size_hint_y=None, height=dp(25), color=(0.8, 0.8, 0.8, 1)
        ))
        self.file_label = Label(
            text="Koi file select nahi hui", size_hint_y=None, height=dp(35),
            color=(0.6, 0.6, 0.6, 1), font_size='12sp'
        )
        self.file_label.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        layout.add_widget(self.file_label)
        layout.add_widget(make_button("Browse File", (0.2, 0.4, 0.7, 1), self.open_file_picker))

        layout.add_widget(make_button("Step 2: Extract Text & Clean Pages", (0.4, 0.2, 0.8, 1), self.process_phase1))

        self.status1 = Label(
            text="Status: Ready", font_size='12sp', size_hint_y=None, height=dp(70),
            color=(0.6, 0.6, 0.6, 1)
        )
        self.status1.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        layout.add_widget(self.status1)

        layout.add_widget(Label(
            text="Step 3: Translated TXT file select karein",
            font_size='14sp', size_hint_y=None, height=dp(25), color=(0.8, 0.8, 0.8, 1)
        ))
        self.txt_label = Label(
            text="Koi TXT select nahi hui", size_hint_y=None, height=dp(35),
            color=(0.6, 0.6, 0.6, 1), font_size='12sp'
        )
        self.txt_label.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        layout.add_widget(self.txt_label)
        layout.add_widget(make_button("Browse TXT", (0.2, 0.4, 0.7, 1), self.open_txt_picker))

        layout.add_widget(make_button("Step 4: Render Translated Pages", (0.1, 0.6, 0.4, 1), self.process_phase2))
        layout.add_widget(make_button("Step 5: Export Final ZIP", (0.8, 0.4, 0.1, 1), self.process_export))

        scroll.add_widget(layout)
        outer.add_widget(scroll)
        self.add_widget(outer)

    def build_topbar(self, title_text):
        bar = BoxLayout(size_hint_y=None, height=dp(50), padding=(10, 5))
        back_btn = make_button("< Back", (0.2, 0.2, 0.25, 1), self.go_home, height=40)
        back_btn.size_hint_x = 0.3
        bar.add_widget(back_btn)
        bar.add_widget(Label(text=title_text, font_size='16sp', color=(1, 1, 1, 1)))
        return bar

    def go_home(self, instance):
        self.manager.transition = SlideTransition(direction='right')
        self.manager.current = 'home'

    def open_file_picker(self, instance):
        popup = FilePickerPopup(
            on_select=self.set_selected_file,
            filters=ext_filters('pdf', 'zip', 'jpg', 'jpeg', 'png', 'webp')
        )
        popup.open()

    def set_selected_file(self, path):
        self.selected_file = path
        self.file_label.text = f"Selected: {os.path.basename(path)}"

    def open_txt_picker(self, instance):
        popup = FilePickerPopup(on_select=self.set_selected_txt, filters=ext_filters('txt'))
        popup.open()

    def set_selected_txt(self, path):
        self.selected_txt = path
        self.txt_label.text = f"Selected: {os.path.basename(path)}"

    def update_status(self, text):
        Clock.schedule_once(lambda dt: setattr(self.status1, 'text', text))

    def process_phase1(self, instance):
        if not self.selected_file or not os.path.exists(self.selected_file):
            self.status1.text = "Error: Pehle ek file select karein!"
            return
        self.status1.text = "Processing Phase 1... Wait karein!"
        def worker():
            try:
                txt_path = run_phase1(self.selected_file)
                self.update_status(f"Phase 1 Done!\nTXT Saved To:\n{txt_path}")
            except Exception as e:
                self.update_status(f"Phase 1 Error: {str(e)}")
        threading.Thread(target=worker, daemon=True).start()

    def process_phase2(self, instance):
        if not self.selected_txt or not os.path.exists(self.selected_txt):
            self.status1.text = "Error: Pehle translated TXT select karein!"
            return
        self.status1.text = "Rendering Translated Pages... Wait karein!"
        def worker():
            try:
                run_phase2(self.selected_txt)
                self.update_status("Manga Rendered Successfully!")
            except Exception as e:
                self.update_status(f"Rendering Error: {str(e)}")
        threading.Thread(target=worker, daemon=True).start()

    def process_export(self, instance):
        self.status1.text = "Exporting ZIP... Wait karein!"
        def worker():
            try:
                zip_path = create_final_zip()
                self.update_status(f"Export Success!\nZIP Saved To:\n{zip_path}")
            except Exception as e:
                self.update_status(f"Export Error: {str(e)}")
        threading.Thread(target=worker, daemon=True).start()


# ============================================================
# Manual Mode Screen
# ============================================================
class ManualModeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_file = ""
        self.pages = []

        outer = BoxLayout(orientation='vertical')
        outer.add_widget(self.build_topbar())

        self.body = BoxLayout(orientation='vertical', padding=15, spacing=12)
        self.show_format_step()
        outer.add_widget(self.body)

        self.add_widget(outer)

    def build_topbar(self):
        bar = BoxLayout(size_hint_y=None, height=dp(50), padding=(10, 5))
        back_btn = make_button("< Back", (0.2, 0.2, 0.25, 1), self.go_home, height=40)
        back_btn.size_hint_x = 0.3
        bar.add_widget(back_btn)
        bar.add_widget(Label(text="Manual Mode", font_size='16sp', color=(1, 1, 1, 1)))
        return bar

    def go_home(self, instance):
        self.manager.transition = SlideTransition(direction='right')
        self.manager.current = 'home'

    def clear_body(self):
        self.body.clear_widgets()

    def show_format_step(self):
        self.clear_body()
        self.body.add_widget(Label(
            text="File format select karein:", font_size='16sp',
            size_hint_y=None, height=dp(35), color=(0.8, 0.8, 0.8, 1)
        ))
        row = BoxLayout(size_hint_y=None, height=dp(60), spacing=10)
        row.add_widget(make_button("PDF", (0.4, 0.2, 0.8, 1), lambda x: self.open_picker(ext_filters('pdf'))))
        row.add_widget(make_button("ZIP", (0.2, 0.5, 0.7, 1), lambda x: self.open_picker(ext_filters('zip'))))
        row.add_widget(make_button("JPG/PNG", (0.1, 0.6, 0.4, 1), lambda x: self.open_picker(ext_filters('jpg', 'jpeg', 'png', 'webp'))))
        self.body.add_widget(row)
        self.body.add_widget(Label())

    def open_picker(self, filters):
        popup = FilePickerPopup(on_select=self.on_file_selected, filters=filters)
        popup.open()

    def on_file_selected(self, path):
        self.selected_file = path
        self.show_loading_step()

    def show_loading_step(self):
        self.clear_body()
        self.body.add_widget(Label(
            text=f"Converting pages in background...\n{os.path.basename(self.selected_file)}",
            font_size='14sp', color=(0.8, 0.8, 0.8, 1)
        ))
        def worker():
            try:
                target_out = os.path.join(WORK_DIR, "temp_pages")
                convert_to_images(self.selected_file, target_out)
                self.pages = get_page_paths(target_out)
                Clock.schedule_once(lambda dt: self.show_gallery_step())
            except Exception as e:
                err_text = str(e)
                Clock.schedule_once(lambda dt: self.show_error_step(err_text))

        threading.Thread(target=worker, daemon=True).start()

    def show_error_step(self, error_msg):
        self.clear_body()
        self.body.add_widget(Label(text=f"Error: {error_msg}", color=(1, 0.4, 0.4, 1)))
        self.body.add_widget(make_button("Try Again", (0.4, 0.2, 0.8, 1), lambda x: self.show_format_step()))

    def show_gallery_step(self):
        self.clear_body()
        if not self.pages:
            self.show_error_step("Is file mein koi pages nahi mile.")
            return

        self.body.add_widget(Label(
            text=f"{len(self.pages)} Pages Found",
            font_size='14sp', size_hint_y=None, height=dp(30), color=(0.8, 0.8, 0.8, 1)
        ))

        scroll = ScrollView(size_hint=(1, 1))
        grid = GridLayout(cols=1, size_hint_y=None, spacing=6)
        grid.bind(minimum_height=grid.setter('height'))

        for idx, page_path in enumerate(self.pages):
            row = BoxLayout(size_hint_y=None, height=dp(70), spacing=8, padding=(5, 5))
            thumb = KivyImage(source=page_path, size_hint_x=None, width=dp(55))
            label = Label(text=f"Page {idx+1:02d}\n{os.path.basename(page_path)}",
                          font_size='12sp', halign='left', valign='middle')
            label.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
            row.add_widget(thumb)
            row.add_widget(label)
            row.add_widget(make_button("Open >", (0.3, 0.3, 0.35, 1), lambda x, p=page_path: self.open_viewer(p), height=40))
            grid.add_widget(row)

        scroll.add_widget(grid)
        self.body.add_widget(scroll)

    def open_viewer(self, page_path):
        popup = Popup(title=os.path.basename(page_path), size_hint=(0.98, 0.98))
        layout = BoxLayout(orientation='vertical')
        img = KivyImage(source=page_path, allow_stretch=True)
        layout.add_widget(img)
        close_btn = make_button("Close", (0.6, 0.2, 0.2, 1), lambda x: popup.dismiss())
        layout.add_widget(close_btn)
        popup.content = layout
        popup.open()


# ============================================================
# Entry Point
# ============================================================
class MangaApp(App):
    def build(self):
        request_android_permissions()
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(OldModeScreen(name='old_mode'))
        sm.add_widget(ManualModeScreen(name='manual_mode'))
        return sm


if __name__ == '__main__':
    MangaApp().run()
