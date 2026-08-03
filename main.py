import os
import json
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.image import Image as KivyImage
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.graphics import Color, Line, Rectangle

from translator_engine import (
    run_phase1, run_phase2, create_final_zip,
    convert_to_images, get_page_paths, run_manual_compile
)

Window.clearcolor = (0.07, 0.07, 0.09, 1)

if os.path.exists("/storage/emulated/0"):
    STORAGE_ROOT = "/storage/emulated/0"
elif os.path.exists("/sdcard"):
    STORAGE_ROOT = "/sdcard"
else:
    STORAGE_ROOT = os.path.expanduser("~")

WORK_DIR = os.path.join(STORAGE_ROOT, "MangaTranslatorWorkspace")
try:
    os.makedirs(WORK_DIR, exist_ok=True)
except Exception:
    # FIX (crash-on-launch): this ran at module import time, before any
    # permission is granted. On Android 11+, without "All files access"
    # granted yet (which can't happen until the user taps the button in
    # the app itself), writing to STORAGE_ROOT raises PermissionError —
    # and since this was unguarded at the top level, it crashed the app
    # instantly on every launch, before the UI even appeared.
    # Fall back to the app's own private folder, which is always writable
    # without any permission at all.
    WORK_DIR = os.path.join(os.path.expanduser("~"), "MangaTranslatorWorkspace")
    os.makedirs(WORK_DIR, exist_ok=True)


def request_android_permissions():
    try:
        from android.permissions import request_permissions, Permission
        request_permissions([
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE,
        ])
    except Exception:
        pass


def has_all_files_access():
    try:
        from jnius import autoclass
        Build = autoclass('android.os.Build$VERSION')
        sdk_int = Build.SDK_INT
        # MANAGE_EXTERNAL_STORAGE only exists on Android 11+ (API 30+)
        if sdk_int >= 30:
            Environment = autoclass('android.os.Environment')
            return bool(Environment.isExternalStorageManager())
        return True
    except Exception:
        return True


def request_all_files_access():
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
    except Exception as e:
        print("Could not launch file manager permissions:", e)


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
#  File Picker Popup
# ============================================================
class FilePickerPopup(Popup):
    def __init__(self, on_select, filters=None, **kwargs):
        super().__init__(**kwargs)
        self.title = "Select File"
        self.size_hint = (0.95, 0.95)
        self.on_select_callback = on_select

        layout = BoxLayout(orientation='vertical', spacing=8, padding=8)
        self.chooser = FileChooserListView(
            path=STORAGE_ROOT,
            filters=filters or ext_filters('pdf', 'zip', 'jpg', 'jpeg', 'png'),
            dirselect=False,
        )
        layout.add_widget(self.chooser)

        self.path_label = Label(
            text="No file selected", size_hint_y=None, height=dp(30),
            color=(0.7, 0.7, 0.7, 1), font_size='12sp'
        )
        self.chooser.bind(selection=self.on_selection_change)
        layout.add_widget(self.path_label)

        btn_row = BoxLayout(size_hint_y=None, height=dp(50), spacing=8)
        select_btn = make_button("Select", (0.2, 0.6, 0.3, 1), self.confirm_selection)
        cancel_btn = make_button("Cancel", (0.6, 0.2, 0.2, 1), lambda x: self.dismiss())
        btn_row.add_widget(select_btn)
        btn_row.add_widget(cancel_btn)
        layout.add_widget(btn_row)

        self.content = layout

    def on_selection_change(self, instance, selection):
        if selection:
            self.path_label.text = os.path.basename(selection[0])

    def confirm_selection(self, instance):
        if self.chooser.selection:
            selected_path = self.chooser.selection[0]
            self.dismiss()
            self.on_select_callback(selected_path)


# ============================================================
#  Home Screen
# ============================================================
class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=30, spacing=20)
        self.add_widget(self.layout)
        self.rebuild()

    def on_pre_enter(self):
        self.rebuild()

    def rebuild(self):
        self.layout.clear_widgets()

        title = Label(
            text="[b]Manga Offline Subber Pro[/b]",
            markup=True, font_size='22sp', size_hint_y=None, height=dp(50),
            color=(0.7, 0.5, 1, 1)
        )
        self.layout.add_widget(title)

        if not has_all_files_access():
            self.layout.add_widget(Label(
                text="Please grant Storage Access to load and edit files:",
                font_size='13sp', size_hint_y=None, height=dp(40),
                color=(1, 0.6, 0.4, 1)
            ))
            self.layout.add_widget(make_button(
                "Grant Storage Access", (0.8, 0.4, 0.1, 1),
                self.grant_access, height=55
            ))
            return

        btn_old = make_button("Old Mode (Auto OCR/Align)", (0.4, 0.2, 0.8, 1), lambda x: self.goto('old_mode'), height=60)
        btn_manual = make_button("Manual Mode (Draw Bubbles)", (0.1, 0.6, 0.4, 1), lambda x: self.goto('manual_mode'), height=60)
        btn_settings = make_button("Global Settings", (0.3, 0.3, 0.35, 1), lambda x: self.goto('settings'), height=50)

        self.layout.add_widget(btn_old)
        self.layout.add_widget(btn_manual)
        self.layout.add_widget(btn_settings)
        self.layout.add_widget(Label())  # Spacer

    def grant_access(self, instance):
        request_all_files_access()

    def goto(self, screen_name):
        self.manager.transition = SlideTransition(direction='left')
        self.manager.current = screen_name


# ============================================================
#  Settings Screen
# ============================================================
class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        layout = BoxLayout(orientation='vertical', padding=20, spacing=15)

        layout.add_widget(Label(text="Global Font Settings", font_size='18sp', size_hint_y=None, height=dp(40), color=(0.7, 0.5, 1, 1)))

        layout.add_widget(Label(text="Default Font Size (PIL Rendering):", size_hint_y=None, height=dp(25)))
        self.font_size_input = TextInput(text="24", multiline=False, size_hint_y=None, height=dp(40))
        layout.add_widget(self.font_size_input)

        layout.add_widget(Label(text="Custom TTF Font Path (Optional):", size_hint_y=None, height=dp(25)))
        self.font_path_label = Label(text="Using Default System Font", size_hint_y=None, height=dp(30), font_size='12sp', color=(0.6, 0.6, 0.6, 1))
        layout.add_widget(self.font_path_label)
        layout.add_widget(make_button("Select Custom Font (.ttf)", (0.2, 0.4, 0.7, 1), self.pick_ttf))

        layout.add_widget(Label())  # Spacer

        btn_row = BoxLayout(size_hint_y=None, height=dp(50), spacing=10)
        btn_row.add_widget(make_button("Save", (0.1, 0.6, 0.4, 1), self.save_settings))
        btn_row.add_widget(make_button("Back", (0.6, 0.2, 0.2, 1), self.go_back))
        layout.add_widget(btn_row)

        self.add_widget(layout)

    def on_pre_enter(self):
        self.font_size_input.text = str(self.app.user_data.get('font_size', 24))
        self.font_path_label.text = os.path.basename(self.app.user_data.get('font_path', '')) or "Using Default System Font"

    def pick_ttf(self, instance):
        popup = FilePickerPopup(on_select=self.set_font_path, filters=ext_filters('ttf'))
        popup.open()

    def set_font_path(self, path):
        self.app.user_data['font_path'] = path
        self.font_path_label.text = os.path.basename(path)

    def save_settings(self, instance):
        try:
            self.app.user_data['font_size'] = int(self.font_size_input.text)
        except ValueError:
            self.app.user_data['font_size'] = 24
        self.app.save_user_data()
        self.go_back()

    def go_back(self, *args):
        self.manager.transition = SlideTransition(direction='right')
        self.manager.current = 'home'


# ============================================================
#  Old Mode Screen (Auto Mode Pipeline)
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

        layout.add_widget(Label(text="Step 1: Select Manga (PDF/ZIP/JPG)", font_size='14sp', size_hint_y=None, height=dp(25)))
        self.file_label = Label(text="No file selected", size_hint_y=None, height=dp(35), color=(0.6, 0.6, 0.6, 1), font_size='12sp')
        layout.add_widget(self.file_label)
        layout.add_widget(make_button("Browse File", (0.2, 0.4, 0.7, 1), self.open_file_picker))

        btn_phase1 = make_button("Step 2: Extract Text & Clean Pages", (0.4, 0.2, 0.8, 1), self.process_phase1)
        layout.add_widget(btn_phase1)

        self.status1 = Label(text="Status: Ready", font_size='12sp', size_hint_y=None, height=dp(60), color=(0.6, 0.6, 0.6, 1))
        self.status1.text_size = (Window.width - 40, None)
        layout.add_widget(self.status1)

        layout.add_widget(Label(text="Step 3: Select Translated Text", font_size='14sp', size_hint_y=None, height=dp(25)))
        self.txt_label = Label(text="No text file selected", size_hint_y=None, height=dp(35), color=(0.6, 0.6, 0.6, 1), font_size='12sp')
        layout.add_widget(self.txt_label)
        layout.add_widget(make_button("Browse TXT", (0.2, 0.4, 0.7, 1), self.open_txt_picker))

        btn_phase2 = make_button("Step 4: Render Translated Pages", (0.1, 0.6, 0.4, 1), self.process_phase2)
        layout.add_widget(btn_phase2)

        btn_export = make_button("Step 5: Export Final ZIP", (0.8, 0.4, 0.1, 1), self.process_export)
        layout.add_widget(btn_export)

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
        popup = FilePickerPopup(on_select=self.set_selected_file, filters=ext_filters('pdf', 'zip', 'jpg', 'jpeg', 'png'))
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

    def process_phase1(self, instance):
        if not self.selected_file or not os.path.exists(self.selected_file):
            self.status1.text = "Please select a file first."
            return
        self.status1.text = "Processing extraction..."
        try:
            txt_path = run_phase1(self.selected_file, WORK_DIR)
            self.status1.text = f"Extraction complete! Saved to:\n{txt_path}"
        except Exception as e:
            self.status1.text = f"Extraction Error: {str(e)}"

    def process_phase2(self, instance):
        if not self.selected_txt or not os.path.exists(self.selected_txt):
            self.status1.text = "Please select your translated text file."
            return
        self.status1.text = "Rendering text onto pages..."
        try:
            run_phase2(self.selected_txt, WORK_DIR)
            self.status1.text = "Rendering complete!"
        except Exception as e:
            self.status1.text = f"Error: {str(e)}"

    def process_export(self, instance):
        # Prevent silent failures: Check if rendered pages exist
        final_dir = os.path.join(WORK_DIR, "final_pages")
        if not os.path.exists(final_dir) or not [f for f in os.listdir(final_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]:
            self.status1.text = "Error: Rendered final pages directory is empty. Complete Step 4 first."
            return

        try:
            zip_path = create_final_zip(WORK_DIR)
            self.status1.text = f"Exported successfully! Saved to:\n{zip_path}"
        except Exception as e:
            self.status1.text = f"Export Error: {str(e)}"


# ============================================================
#  Manual Mode Screen (Gallery / Loader Interface)
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
        bar.add_widget(Label(text="Manual Mode Canvas", font_size='16sp', color=(1, 1, 1, 1)))
        return bar

    def go_home(self, instance):
        self.manager.transition = SlideTransition(direction='right')
        self.manager.current = 'home'

    def clear_body(self):
        self.body.clear_widgets()

    def show_format_step(self):
        self.clear_body()
        self.body.add_widget(Label(text="Select Import Format:", font_size='16sp', size_hint_y=None, height=dp(35)))
        row = BoxLayout(size_hint_y=None, height=dp(60), spacing=10)
        row.add_widget(make_button("PDF", (0.4, 0.2, 0.8, 1), lambda x: self.open_picker(ext_filters('pdf'))))
        row.add_widget(make_button("ZIP", (0.2, 0.5, 0.7, 1), lambda x: self.open_picker(ext_filters('zip'))))
        row.add_widget(make_button("JPG/PNG", (0.1, 0.6, 0.4, 1), lambda x: self.open_picker(ext_filters('jpg', 'jpeg', 'png'))))
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
        self.body.add_widget(Label(text=f"Importing and Splitting Pages:\n{os.path.basename(self.selected_file)}", font_size='14sp'))
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: self.do_convert(), 0.3)

    def do_convert(self):
        try:
            temp_dir = os.path.join(WORK_DIR, "manual_pages")
            convert_to_images(self.selected_file, temp_dir)
            self.pages = get_page_paths(temp_dir)
            self.show_gallery_step()
        except Exception as e:
            self.clear_body()
            self.body.add_widget(Label(text=f"Failed to load: {str(e)}", color=(1, 0.4, 0.4, 1)))
            self.body.add_widget(make_button("Retry", (0.4, 0.2, 0.8, 1), lambda x: self.show_format_step()))

    def show_gallery_step(self):
        self.clear_body()
        if not self.pages:
            self.body.add_widget(Label(text="No renderable pages found.", color=(1, 0.4, 0.4, 1)))
            self.body.add_widget(make_button("Retry", (0.4, 0.2, 0.8, 1), lambda x: self.show_format_step()))
            return

        header = BoxLayout(size_hint_y=None, height=dp(40))
        header.add_widget(Label(text=f"{len(self.pages)} Pages Detected - Tap to Edit", font_size='14sp', color=(0.8, 0.8, 0.8, 1)))
        compile_btn = make_button("Compile Manual", (0.8, 0.4, 0.1, 1), self.compile_manual, height=35)
        compile_btn.size_hint_x = 0.4
        header.add_widget(compile_btn)
        self.body.add_widget(header)

        scroll = ScrollView(size_hint=(1, 1))
        grid = GridLayout(cols=1, size_hint_y=None, spacing=8)
        grid.bind(minimum_height=grid.setter('height'))

        for idx, page_path in enumerate(self.pages):
            row = BoxLayout(size_hint_y=None, height=dp(80), spacing=8, padding=(5, 5))
            thumb = KivyImage(source=page_path, size_hint_x=None, width=dp(60))
            label = Label(text=f"Page {idx+1:02d}\n{os.path.basename(page_path)}", font_size='12sp', halign='left')
            row.add_widget(thumb)
            row.add_widget(label)
            row.add_widget(make_button("Draw >", (0.1, 0.6, 0.4, 1), lambda x, p=page_path: self.open_manual_editor(p), height=50))
            grid.add_widget(row)

        scroll.add_widget(grid)
        self.body.add_widget(scroll)

    def open_manual_editor(self, page_path):
        editor = InteractiveCanvasPopup(page_path=page_path)
        editor.open()

    def compile_manual(self, instance):
        try:
            zip_path = run_manual_compile(WORK_DIR, App.get_running_app().user_data)
            self.clear_body()
            self.body.add_widget(Label(text=f"Compilation successful!\nSaved to:\n{zip_path}", color=(0.4, 1, 0.4, 1)))
            self.body.add_widget(make_button("Finish", (0.1, 0.6, 0.4, 1), lambda x: self.show_format_step()))
        except Exception as e:
            self.clear_body()
            self.body.add_widget(Label(text=f"Compilation Error:\n{str(e)}", color=(1, 0.4, 0.4, 1)))
            self.body.add_widget(make_button("Back", (0.6, 0.2, 0.2, 1), lambda x: self.show_gallery_step()))


# ============================================================
#  Interactive Editor Window (Tap to Draw / Translate)
# ============================================================
class InteractiveCanvasPopup(Popup):
    def __init__(self, page_path, **kwargs):
        super().__init__(**kwargs)
        self.page_path = page_path
        self.page_name = os.path.basename(page_path)
        self.title = f"Editing: {self.page_name}"
        self.size_hint = (0.98, 0.98)

        self.app = App.get_running_app()
        self.annotations = self.app.user_data.get('manual_annotations', {})
        if self.page_name not in self.annotations:
            self.annotations[self.page_name] = []

        self.root_layout = BoxLayout(orientation='vertical', spacing=8, padding=6)

        self.canvas_container = BoxLayout(size_hint=(1, 0.75))
        self.img_widget = KivyImage(source=self.page_path, allow_stretch=True)
        self.img_widget.bind(on_touch_down=self.handle_canvas_tap)
        self.canvas_container.add_widget(self.img_widget)
        self.root_layout.add_widget(self.canvas_container)

        self.info_lbl = Label(text="Tap on the Manga Page to add text bubble locations.", size_hint_y=None, height=dp(25), font_size='12sp')
        self.root_layout.add_widget(self.info_lbl)

        btn_bar = BoxLayout(size_hint_y=None, height=dp(50), spacing=8)
        btn_bar.add_widget(make_button("Clear Markers", (0.8, 0.2, 0.2, 1), self.clear_markers))
        btn_bar.add_widget(make_button("Save & Return", (0.1, 0.6, 0.4, 1), self.save_and_exit))
        self.root_layout.add_widget(btn_bar)

        self.content = self.root_layout
        self.draw_overlay_markers()

    def draw_overlay_markers(self):
        self.img_widget.canvas.after.clear()
        with self.img_widget.canvas.after:
            for item in self.annotations[self.page_name]:
                norm_x, norm_y = item['pos']
                
                px = self.img_widget.x + (norm_x * self.img_widget.norm_image_size[0]) + (self.img_widget.width - self.img_widget.norm_image_size[0])/2
                py = self.img_widget.y + (norm_y * self.img_widget.norm_image_size[1]) + (self.img_widget.height - self.img_widget.norm_image_size[1])/2
                
                Color(0.9, 0.1, 0.1, 0.8)
                Line(circle=(px, py, dp(15)), width=dp(2))
                Color(0, 0, 0, 0.5)
                Rectangle(pos=(px-dp(6), py-dp(6)), size=(dp(12), dp(12)))

    def handle_canvas_tap(self, instance, touch):
        if not self.img_widget.collide_point(*touch.pos):
            return False

        iw, ih = self.img_widget.norm_image_size
        offset_x = (self.img_widget.width - iw) / 2
        offset_y = (self.img_widget.height - ih) / 2

        rel_x = touch.x - self.img_widget.x - offset_x
        rel_y = touch.y - self.img_widget.y - offset_y

        if 0 <= rel_x <= iw and 0 <= rel_y <= ih:
            norm_x = rel_x / iw
            norm_y = rel_y / ih
            self.prompt_bubble_text(norm_x, norm_y)
            return True

    def prompt_bubble_text(self, norm_x, norm_y):
        prompt = Popup(title="Configure Bubble Settings", size_hint=(0.9, 0.6))
        layout = BoxLayout(orientation='vertical', padding=10, spacing=8)

        text_input = TextInput(hint_text="Enter Translation text...", multiline=True)
        layout.add_widget(text_input)

        row_cfg = BoxLayout(size_hint_y=None, height=dp(40), spacing=5)
        row_cfg.add_widget(Label(text="Box Width:"))
        width_in = TextInput(text="180", multiline=False)
        row_cfg.add_widget(width_in)
        layout.add_widget(row_cfg)

        row_color = BoxLayout(size_hint_y=None, height=dp(40), spacing=5)
        row_color.add_widget(Label(text="Text Color (RGB):"))
        color_in = TextInput(text="0,0,0", multiline=False)
        row_color.add_widget(color_in)
        layout.add_widget(row_color)

        def add_item(btn):
            width_px = 180
            try:
                width_px = int(width_in.text)
            except ValueError:
                pass

            if text_input.text.strip():
                new_item = {
                    'pos': [norm_x, norm_y],
                    'text': text_input.text.strip(),
                    'box_w': width_px,
                    'color': color_in.text.strip()
                }
                self.annotations[self.page_name].append(new_item)
                self.draw_overlay_markers()
            prompt.dismiss()

        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=8)
        btn_row.add_widget(make_button("Add", (0.1, 0.6, 0.4, 1), add_item))
        btn_row.add_widget(make_button("Cancel", (0.6, 0.2, 0.2, 1), lambda x: prompt.dismiss()))
        layout.add_widget(btn_row)

        prompt.content = layout
        prompt.open()

    def clear_markers(self, instance):
        self.annotations[self.page_name] = []
        self.img_widget.canvas.after.clear()
        self.draw_overlay_markers()

    def save_and_exit(self, instance):
        self.app.user_data['manual_annotations'] = self.annotations
        self.app.save_user_data()
        self.dismiss()


# ============================================================
#  Core App Runner
# ============================================================
class MangaApp(App):
    def build(self):
        self.user_data_path = os.path.join(WORK_DIR, "config.json")
        self.load_user_data()

        request_android_permissions()
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(OldModeScreen(name='old_mode'))
        sm.add_widget(ManualModeScreen(name='manual_mode'))
        sm.add_widget(SettingsScreen(name='settings'))
        return sm

    def load_user_data(self):
        if os.path.exists(self.user_data_path):
            try:
                with open(self.user_data_path, 'r') as f:
                    self.user_data = json.load(f)
            except Exception:
                self.user_data = {}
        else:
            self.user_data = {}

        if 'font_size' not in self.user_data:
            self.user_data['font_size'] = 24
        if 'font_path' not in self.user_data:
            self.user_data['font_path'] = ""
        if 'manual_annotations' not in self.user_data:
            self.user_data['manual_annotations'] = {}

    def save_user_data(self):
        try:
            with open(self.user_data_path, 'w') as f:
                json.dump(self.user_data, f, indent=4)
        except Exception as e:
            print("Failed to save configuration:", e)


if __name__ == '__main__':
    MangaApp().run()
