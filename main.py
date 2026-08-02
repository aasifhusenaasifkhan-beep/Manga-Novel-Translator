import os, zipfile, shutil
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelHeader
from kivy.graphics import Color, Rectangle
from kivy.core.window import Window
from translator_engine import run_phase1, run_phase2, create_final_zip

# Set Dark Theme Background
Window.clearcolor = (0.07, 0.07, 0.09, 1)

class MangaTranslatorUI(TabbedPanel):
    def __init__(self, **kwargs):
        super(MangaTranslatorUI, self).__init__(**kwargs)
        self.do_default_tab = False
        self.background_color = (0.1, 0.1, 0.12, 1)

        # Tab 1: Workflow Tab
        tab_main = TabbedPanelHeader(text='🎨 Workflow')
        tab_main.content = self.create_workflow_tab()
        self.add_widget(tab_main)

        # Tab 2: Settings Tab
        tab_settings = TabbedPanelHeader(text='⚙️ Settings & API')
        tab_settings.content = self.create_settings_tab()
        self.add_widget(tab_settings)

    def create_workflow_tab(self):
        scroll = ScrollView(size_hint=(1, 1))
        layout = BoxLayout(orientation='vertical', padding=15, spacing=12, size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))

        # Header Title
        title = Label(
            text="[b]Manga & Novel Offline Subber Pro[/b]", 
            markup=True, font_size='22sp', size_hint_y=None, height=40, color=(0.7, 0.5, 1, 1)
        )
        layout.add_widget(title)

        # File Input Box (Manual Path / Download Picker)
        layout.add_widget(Label(text="File Path (PDF/ZIP/JPG):", font_size='14sp', size_hint_y=None, height=25, color=(0.8, 0.8, 0.8, 1)))
        self.input_file_path = TextInput(
            text="/sdcard/Download/input.pdf", multiline=False, size_hint_y=None, height=45,
            background_color=(0.15, 0.15, 0.2, 1), foreground_color=(1, 1, 1, 1)
        )
        layout.add_widget(self.input_file_path)

        # Step 1 Button
        btn_phase1 = Button(
            text="🚀 Step 1: Extract Text & Clean Pages", size_hint_y=None, height=50,
            background_color=(0.4, 0.2, 0.8, 1), background_normal=''
        )
        btn_phase1.bind(on_release=self.process_phase1)
        layout.add_widget(btn_phase1)

        # Status Label
        self.status1 = Label(text="Status: Ready", font_size='12sp', size_hint_y=None, height=35, color=(0.6, 0.6, 0.6, 1))
        layout.add_widget(self.status1)

        # Step 2: Translated TXT Input
        layout.add_widget(Label(text="Translated TXT File Path:", font_size='14sp', size_hint_y=None, height=25, color=(0.8, 0.8, 0.8, 1)))
        self.input_txt_path = TextInput(
            text="/sdcard/Download/translate_me.txt", multiline=False, size_hint_y=None, height=45,
            background_color=(0.15, 0.15, 0.2, 1), foreground_color=(1, 1, 1, 1)
        )
        layout.add_widget(self.input_txt_path)

        # Step 3 Button
        btn_phase2 = Button(
            text="🎯 Step 2: Render Translated Manga Pages", size_hint_y=None, height=50,
            background_color=(0.1, 0.6, 0.4, 1), background_normal=''
        )
        btn_phase2.bind(on_release=self.process_phase2)
        layout.add_widget(btn_phase2)

        # Step 4 Button (Export ZIP)
        btn_export = Button(
            text="📦 Step 3: Export Final Translated ZIP", size_hint_y=None, height=50,
            background_color=(0.8, 0.4, 0.1, 1), background_normal=''
        )
        btn_export.bind(on_release=self.process_export)
        layout.add_widget(btn_export)

        scroll.add_widget(layout)
        return scroll

    def create_settings_tab(self):
        layout = BoxLayout(orientation='vertical', padding=20, spacing=15)

        layout.add_widget(Label(text="[b]API Key & Prompt Settings[/b]", markup=True, font_size='18sp', size_hint_y=None, height=40, color=(0.7, 0.5, 1, 1)))

        layout.add_widget(Label(text="API Key (Gemini / OpenAI / DeepL):", size_hint_y=None, height=25))
        self.api_key_input = TextInput(password=True, multiline=False, size_hint_y=None, height=45, background_color=(0.15, 0.15, 0.2, 1), foreground_color=(1, 1, 1, 1))
        layout.add_widget(self.api_key_input)

        layout.add_widget(Label(text="System Prompt (Introduction):", size_hint_y=None, height=25))
        self.prompt_input = TextInput(
            text="Translate Japanese Manga dialogues into Hindi naturally keeping comic slang.",
            multiline=True, size_hint_y=None, height=100, background_color=(0.15, 0.15, 0.2, 1), foreground_color=(1, 1, 1, 1)
        )
        layout.add_widget(self.prompt_input)

        btn_save = Button(text="💾 Save Settings", size_hint_y=None, height=50, background_color=(0.2, 0.5, 0.9, 1), background_normal='')
        layout.add_widget(btn_save)

        return layout

    def process_phase1(self, instance):
        file_path = self.input_file_path.text.strip()
        if not os.path.exists(file_path):
            self.status1.text = f"❌ File nahi mili: {file_path}"
            return
        self.status1.text = "⏳ Processing Phase 1... Wait karein!"
        try:
            txt_path = run_phase1(file_path)
            self.status1.text = f"✅ Phase 1 Done! TXT saved to:\n{txt_path}"
        except Exception as e:
            self.status1.text = f"❌ Error: {str(e)}"

    def process_phase2(self, instance):
        txt_path = self.input_txt_path.text.strip()
        if not os.path.exists(txt_path):
            self.status1.text = f"❌ Translated TXT nahi mila: {txt_path}"
            return
        self.status1.text = "⏳ Rendering Manga Pages... Wait karein!"
        try:
            res = run_phase2(txt_path)
            self.status1.text = f"✅ Manga Rendered Successfully in 'final_pages'!"
        except Exception as e:
            self.status1.text = f"❌ Error: {str(e)}"

    def process_export(self, instance):
        try:
            zip_path = create_final_zip()
            self.status1.text = f"🎉 Final ZIP Exported To:\n{zip_path}"
        except Exception as e:
            self.status1.text = f"❌ Export Error: {str(e)}"

class MangaApp(App):
    def build(self):
        return MangaTranslatorUI()

if __name__ == '__main__':
    MangaApp().run()
