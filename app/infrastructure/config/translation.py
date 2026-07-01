from typing import Dict


class TranslationManager:
    """Manages active application language and string dictionary lookups."""

    _active_lang: str = "en"

    # English & Vietnamese translation dictionaries
    _dictionary: Dict[str, Dict[str, str]] = {
        "en": {
            # Navigation
            "nav.projects": "Projects",
            "nav.downloader": "Downloader",
            "nav.transcribe": "Transcribe",
            "nav.enhancer": "Enhancer",
            "nav.workflow": "Workflow",
            "nav.settings": "Settings",
            
            # Projects View
            "proj.welcome": "Welcome to FramePilot",
            "proj.active_ws": "Active Workspace: {}",
            "proj.create_title": "Create New Project",
            "proj.name_label": "Project Name:",
            "proj.path_label": "Project Path:",
            "proj.browse": "Browse",
            "proj.create_btn": "Create Workspace",
            "proj.select_title": "Select Existing Workspace",
            "proj.load_btn": "Load Workspace",
            "proj.none_ws": "None (Select/Create a workspace)",
            
            # Downloader View
            "dl.title": "Video & Image Downloader",
            "dl.url_lbl": "Video URL:",
            "dl.dest_lbl": "Output Folder:",
            "dl.start_btn": "Start Download",
            
            # STT View
            "stt.title": "Speech to Text & Transcription",
            "stt.file_lbl": "Media File:",
            "stt.provider_lbl": "Provider:",
            "stt.model_lbl": "Model:",
            "stt.lang_lbl": "Language:",
            "stt.task_lbl": "Task:",
            "stt.format_lbl": "Output Format:",
            "stt.btn": "Transcribe File",
            
            # Enhancer View
            "enh.title": "Quality Enhancement Center",
            "enh.file_lbl": "Source Media File:",
            "enh.res_lbl": "Target Resolution:",
            "enh.type_lbl": "Enhancer Type:",
            "enh.btn": "Enhance Media",
            
            # Workflow View
            "wf.title": "Visual Workflow Builder",
            "wf.btn_dl": "Add Download Node",
            "wf.btn_stt": "Add Transcribe Node",
            "wf.btn_trans": "Add Translate Node",
            "wf.btn_tts": "Add TTS Node",
            "wf.btn_clear": "Clear Canvas",
            "wf.btn_run": "Execute Workflow",
            
            # Settings View
            "set.title": "Global Settings & Configuration",
            "set.theme": "Application Theme:",
            "set.lang": "Application Language:",
            "set.storage": "Default Storage Path:",
            "set.openai": "OpenAI API Key:",
            "set.deepseek": "DeepSeek API Key:",
            "set.gpu": "GPU Acceleration:",
            "set.save_btn": "Save Settings",
            "set.saved_msg": "Configuration saved successfully! Please restart the app to apply language settings.",
        },
        "vi": {
            # Navigation
            "nav.projects": "Dự án",
            "nav.downloader": "Tải Video",
            "nav.transcribe": "Phụ đề (STT)",
            "nav.enhancer": "Nâng cấp Video",
            "nav.workflow": "Quy trình tự động",
            "nav.settings": "Cài đặt",
            
            # Projects View
            "proj.welcome": "Chào mừng đến với FramePilot",
            "proj.active_ws": "Dự án Hiện tại: {}",
            "proj.create_title": "Tạo Dự án Mới",
            "proj.name_label": "Tên Dự án:",
            "proj.path_label": "Đường dẫn Dự án:",
            "proj.browse": "Chọn thư mục",
            "proj.create_btn": "Tạo dự án",
            "proj.select_title": "Chọn Dự án Hiện có",
            "proj.load_btn": "Mở dự án",
            "proj.none_ws": "Chưa có (Hãy tạo hoặc chọn một dự án)",
            
            # Downloader View
            "dl.title": "Tải Video & Hình ảnh",
            "dl.url_lbl": "Đường dẫn Video URL:",
            "dl.dest_lbl": "Thư mục Lưu trữ:",
            "dl.start_btn": "Bắt đầu Tải",
            
            # STT View
            "stt.title": "Nhận dạng giọng nói & Phụ đề",
            "stt.file_lbl": "Tệp tin nguồn:",
            "stt.provider_lbl": "Nhà cung cấp:",
            "stt.model_lbl": "Mô hình:",
            "stt.lang_lbl": "Ngôn ngữ:",
            "stt.task_lbl": "Nhiệm vụ:",
            "stt.format_lbl": "Định dạng đầu ra:",
            "stt.btn": "Bắt đầu tạo phụ đề",
            
            # Enhancer View
            "enh.title": "Trung tâm Nâng cao Chất lượng Video",
            "enh.file_lbl": "Tệp tin Video gốc:",
            "enh.res_lbl": "Độ phân giải đích:",
            "enh.type_lbl": "Phương thức xử lý:",
            "enh.btn": "Bắt đầu xử lý",
            
            # Workflow View
            "wf.title": "Thiết lập Quy trình tự động hóa",
            "wf.btn_dl": "Thêm Bước Tải Video",
            "wf.btn_stt": "Thêm Bước Phụ đề (STT)",
            "wf.btn_trans": "Thêm Bước Dịch thuật",
            "wf.btn_tts": "Thêm Bước Lồng tiếng (TTS)",
            "wf.btn_clear": "Xóa Sơ đồ",
            "wf.btn_run": "Chạy Quy trình",
            
            # Settings View
            "set.title": "Cài đặt & Cấu hình Hệ thống",
            "set.theme": "Giao diện Ứng dụng:",
            "set.lang": "Ngôn ngữ Ứng dụng:",
            "set.storage": "Thư mục Lưu trữ Mặc định:",
            "set.openai": "Khóa OpenAI API Key:",
            "set.deepseek": "Khóa Deepseek API Key:",
            "set.gpu": "Tăng tốc phần cứng (GPU):",
            "set.save_btn": "Lưu Cài đặt",
            "set.saved_msg": "Lưu cài đặt thành công! Vui lòng khởi động lại ứng dụng để áp dụng ngôn ngữ mới.",
        }
    }

    @classmethod
    def set_language(cls, lang: str) -> None:
        """Sets the active system language."""
        if lang in cls._dictionary:
            cls._active_lang = lang

    @classmethod
    def translate(cls, key: str) -> str:
        """Translates a key string based on the active language configuration."""
        lang_dict = cls._dictionary.get(cls._active_lang, cls._dictionary["en"])
        return lang_dict.get(key, key)


def tr(key: str) -> str:
    """Convenience helper to retrieve translation for key."""
    return TranslationManager.translate(key)
