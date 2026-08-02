import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from translator_engine import run_phase1

class TranslatorApp(App):
    def build(self):
        self.layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        self.label = Label(text="Manga & Novel Offline Translator", font_size='20sp', size_hint=(1, 0.1))
        self.layout.add_widget(self.label)

        self.btn_select = Button(text="1. File Upload Karein (PDF / ZIP / Image)", size_hint=(1, 0.15), background_color=(0.2, 0.6, 1, 1))
        self.btn_select.bind(on_release=self.open_file_chooser)
        self.layout.add_widget(self.btn_select)

        self.status_label = Label(text="Status: Waiting for file...", size_hint=(1, 0.1))
        self.layout.add_widget(self.status_label)

        return self.layout

    def open_file_chooser(self, instance):
        content = BoxLayout(orientation='vertical')
        filechooser = FileChooserListView()
        content.add_widget(filechooser)

        btn_load = Button(text="Select This File", size_hint=(1, 0.15))
        content.add_widget(btn_load)

        popup = Popup(title="Choose File", content=content, size_hint=(0.9, 0.9))

        def load_file(inst):
            if filechooser.selection:
                selected_file = filechooser.selection[0]
                popup.dismiss()
                self.process_file(selected_file)

        btn_load.bind(on_release=load_file)
        popup.open()

    def process_file(self, file_path):
        self.status_label.text = "Processing... Wait karein!"
        try:
            txt_path = run_phase1(file_path)
            self.status_label.text = f"✅ Done! TXT File Saved:\n{txt_path}"
        except Exception as e:
            self.status_label.text = f"❌ Error: {str(e)}"

if __name__ == '__main__':
    TranslatorApp().run()