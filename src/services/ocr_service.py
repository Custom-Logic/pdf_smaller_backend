"""OCR Service – Job-Oriented Architecture  (sync edition – 2025-09)
Handles Optical Character Recognition for scanned PDFs and images
Returns *disk* meta only – no file_data bytes – to match conversion service.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.services.file_management_service import FileManagementService

logger = logging.getLogger(__name__)

# ---------------- graceful library loading ----------------------------------
try:
    import pytesseract
    from PIL import Image
    OCR_LIBS_AVAILABLE = True
except ImportError:  # pragma: no cover
    OCR_LIBS_AVAILABLE = False
    logging.warning("pytesseract / Pillow unavailable – OCR disabled")

try:
    import fitz  # PyMuPDF
    PDF_LIBS_AVAILABLE = True
except ImportError:  # pragma: no cover
    PDF_LIBS_AVAILABLE = False
    logging.warning("PyMuPDF unavailable – PDF OCR disabled")

# ------------------------------------------------------------------------------


class OCRService:
    """OCR for PDFs and images – crash-hardened, 100 % sync, disk-only output."""

    def __init__(self, file_service: Optional[FileManagementService] = None):
        self.file_service = file_service or FileManagementService()

        self.supported_formats = ("pdf", "png", "jpg", "jpeg", "tiff", "bmp")
        self.supported_languages = [
            "eng", "spa", "fra", "deu", "ita", "por", "rus", "jpn", "kor", "chi_sim", "ara", "hin"
        ]
        self.quality_levels = ("fast", "balanced", "accurate")
        self.output_formats = ("searchable_pdf", "text", "json")
        self.default_quality = "balanced"
        self.default_lang = "eng"

        if OCR_LIBS_AVAILABLE:
            self._configure_tesseract()

    # --------------------------------------------------------------------------
    # PUBLIC ENTRY POINTS – identical signatures
    # --------------------------------------------------------------------------
    def process_ocr_data(
        self,
        file_data: bytes,
        options: Optional[Dict[str, Any]] = None,
        original_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """PDF/image → OCR result.  Never returns bytes; only disk meta."""
        options = options or {}
        ext = self._get_extension(original_filename)
        if ext not in self.supported_formats:
            raise ValueError(f"Unsupported format {ext}")

        temp_file: Optional[Path] = None
        try:
            temp_file = self._save_file_data(file_data, original_filename)
            if ext == "pdf":
                result = self._process_pdf_ocr(temp_file, options)
            else:
                result = self._process_image_ocr(temp_file, options)

            # ====  disk-only meta  ====
            out_path = Path(result["output_path"])
            return {
                "success": True,
                "output_path": str(out_path),
                "filename": out_path.name,
                "mime_type": result["mime_type"],
                "file_size": self.file_service.get_file_size(str(out_path)),
                "original_filename": original_filename,
                "original_size": len(file_data),
            }

        except Exception as exc:
            logger.exception("OCR failed")
            # Clean up any temporary files
            if temp_file:
                self.file_service.delete_file(str(temp_file))
            return {
                "success": False,
                "error": str(exc),
                "original_filename": original_filename,
                "original_size": len(file_data),
            }
        finally:
            if temp_file:
                self.file_service.delete_file(str(temp_file))

    def get_ocr_preview(
        self,
        file_data: bytes,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Light-weight preview; never crashes."""
        options = options or {}
        temp_file: Optional[Path] = None
        try:
            temp_file = self._save_file_data(file_data, "preview.pdf")
            analysis = self._analyze_file_for_ocr(temp_file)
            return {
                "success": True,
                "original_size": len(file_data),
                "estimated_time": self._estimate_ocr_time(analysis, options),
                "complexity": self._assess_ocr_complexity(analysis, options),
                "estimated_accuracy": self._estimate_ocr_accuracy(analysis, options),
                "recommendations": self._get_ocr_recommendations(analysis, options),
                "supported_formats": self.output_formats,
                "supported_languages": self.supported_languages,
            }
        except Exception as exc:
            logger.exception("OCR preview failed")
            # Clean up any temporary files
            if temp_file:
                self.file_service.delete_file(str(temp_file))
            return {
                "success": False,
                "error": str(exc),
                "original_size": len(file_data),
                "estimated_time": 0,
                "complexity": "unknown",
                "estimated_accuracy": 0.0,
                "recommendations": [],
                "supported_formats": self.output_formats,
                "supported_languages": self.supported_languages,
            }
        finally:
            if temp_file:
                self.file_service.delete_file(str(temp_file))

    # --------------------------------------------------------------------------
    # INTERNALS – file handling
    # --------------------------------------------------------------------------
    def _save_file_data(self, data: bytes, name: Optional[str] = None) -> Path:
        """Save file data using file management service"""
        filename = name or f"temp_{uuid.uuid4().hex[:8]}.pdf"
        file_id, file_path = self.file_service.save_file(data, filename)
        return Path(file_path)

    @staticmethod
    def _secure_filename(name: str) -> str:
        return re.sub(r"[^\w.-]", "_", name).strip("_") or "file"

    def _get_extension(self, filename: Optional[str]) -> str:
        if not filename:
            return "pdf"
        return filename.lower().split(".")[-1] if "." in filename else "pdf"

    # --------------------------------------------------------------------------
    # Tesseract config
    # --------------------------------------------------------------------------
    def _configure_tesseract(self) -> None:
        """Try common Tesseract binary paths."""
        for path in (
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
            "/opt/homebrew/bin/tesseract",
        ):
            try:
                pytesseract.pytesseract.tesseract_cmd = path
                _ = pytesseract.get_tesseract_version()
                logger.info("Tesseract found at %s", path)
                break
            except Exception:
                continue
        else:
            logger.error("Tesseract not found – OCR will fail")

    # --------------------------------------------------------------------------
    # ANALYSIS – sync implementations
    # --------------------------------------------------------------------------
    def _analyze_file_for_ocr(self, file_path: Path) -> Dict[str, Any]:
        ext = self._get_extension(file_path.name)
        size = self.file_service.get_file_size(str(file_path))
        base = {"file_type": ext, "file_size": size, "page_count": 1, "image_quality": "medium", "ocr_potential": "medium"}

        if ext == "pdf" and PDF_LIBS_AVAILABLE:
            base.update(self._analyze_pdf_for_ocr(file_path))
        elif ext != "pdf" and OCR_LIBS_AVAILABLE:
            base.update(self._analyze_image_for_ocr(file_path))
        return base

    def _analyze_pdf_for_ocr(self, pdf_path: Path) -> Dict[str, Any]:
        try:
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            sample = min(3, page_count)
            total_images = 0
            text_len = 0
            for page_num in range(sample):
                page = doc.load_page(page_num)
                total_images += len(page.get_images())
                text_len += len(page.get_text().strip())
            doc.close()

            iq = self._assess_image_quality(total_images, page_count)
            op = self._assess_ocr_potential(text_len, total_images, page_count)
            return {"page_count": page_count, "image_quality": iq, "ocr_potential": op, "total_images": total_images, "text_content": text_len}
        except Exception as exc:
            logger.warning("PDF analysis failed: %s", exc)
            return {}

    def _analyze_image_for_ocr(self, img_path: Path) -> Dict[str, Any]:
        try:
            with Image.open(img_path) as img:
                w, h = img.size
                size = self.file_service.get_file_size(str(img_path))
                iq = self._assess_image_quality_by_resolution(w, h, size)
                op = self._assess_image_ocr_potential(img.format, size)
                return {"width": w, "height": h, "format": img.format, "image_quality": iq, "ocr_potential": op}
        except Exception as exc:
            logger.warning("Image analysis failed: %s", exc)
            return {}

    # --------------------------------------------------------------------------
    # OCR PROCESSING – sync, disk-only
    # --------------------------------------------------------------------------
    def _process_pdf_ocr(self, pdf_path: Path, opts: Dict[str, Any]) -> Dict[str, Any]:
        """PDF → searchable PDF **or** text/json on disk."""
        if not PDF_LIBS_AVAILABLE:
            raise RuntimeError("PyMuPDF unavailable")

        output_format = opts.get("outputFormat", "searchable_pdf")
        lang = opts.get("language", self.default_lang)
        quality = opts.get("quality", self.default_quality)

        # ---------- 1.  run OCR on every page ----------
        doc = fitz.open(pdf_path)
        full_text = []
        for page in doc:
            # noinspection PyUnresolvedReferences
            pix = page.get_pixmap(dpi=300)
            img_bytes = pix.tobytes("png")
            full_text.append(self._perform_image_ocr_bytes(img_bytes, lang, quality))
        doc.close()
        ocr_text = "\n".join(full_text)

        # ---------- 2.  return the *correct* disk file ----------
        if output_format == "pdf":
            # make searchable PDF
            doc = fitz.open(pdf_path)  # re-open to copy pages
            out_doc = fitz.open()
            for page in doc:
                # noinspection PyUnresolvedReferences
                new_page = out_doc.new_page(width=page.rect.width, height=page.rect.height)
                new_page.show_pdf_page(page.rect, doc, page.number)
                if ocr_text.strip():
                    new_page.insert_textbox(
                        fitz.Rect(0, 0, page.rect.width, page.rect.height),
                        ocr_text,
                        fontsize=1,
                        color=(0, 0, 0, 0),
                    )
            doc.close()
            filename = f"ocr_{pdf_path.stem}.pdf"
            out_path = self.upload_folder / filename
            out_doc.save(str(out_path))
            out_doc.close()
            return {"output_path": str(out_path), "filename": filename, "mime_type": "application/pdf", "output_format": output_format}

        # ---------- 3.  text or json ----------
        if output_format == "json":
            return self._create_json_output(ocr_text, pdf_path)
        # default = plain text
        return self._create_text_output(ocr_text, pdf_path)

    def _process_image_ocr(self, img_path: Path, opts: Dict[str, Any]) -> Dict[str, Any]:
        """Image → text / json on disk."""
        ...
        ocr_text = self._perform_image_ocr_bytes(img_path.read_bytes(), lang, quality)

        if opts.get('output_format') == "json":
            return self._create_json_output(ocr_text, img_path)
        # default = plain text
        return self._create_text_output(ocr_text, img_path)

    # --------------------------------------------------------------------------
    # low-level OCR
    # --------------------------------------------------------------------------
    def _perform_image_ocr_bytes(self, img_bytes: bytes, lang: str, quality: str) -> str:
        """Run Tesseract on in-memory image – sync."""
        if not OCR_LIBS_AVAILABLE:
            raise RuntimeError("OCR libs not installed")
        import io
        config = self._get_tesseract_config(quality)
        return pytesseract.image_to_string(Image.open(io.BytesIO(img_bytes)), lang=lang, config=config)

    @staticmethod
    def _get_tesseract_config(quality: str) -> str:
        """Always use LSTM engine – legacy data not needed."""
        return {
            "fast": "--oem 1 --psm 6",
            "balanced": "--oem 1 --psm 6",   # changed from 2 → 1
            "accurate": "--oem 1 --psm 6",   # changed from 3 → 1
        }.get(quality, "--oem 1 --psm 6")
    # --------------------------------------------------------------------------
    # output helpers – disk only
    # --------------------------------------------------------------------------
    def _create_text_output(self, text: str, original: Path) -> Dict[str, Any]:
        ...
        return {"output_path": str(out_path), "filename": filename, "mime_type": "text/plain", "output_format": "text"}

    def _create_json_output(self, text: str, original: Path) -> Dict[str, Any]:
        filename = f"ocr_{original.stem}.json"
        out_path = self.upload_folder / filename
        out_path.write_text(
            json.dumps(
                {
                    "text": text,
                    "word_count": len(text.split()),
                    "character_count": len(text),
                    "lines": text.splitlines(),
                    "metadata": {
                        "source_file": original.name,
                        "processed_at": datetime.utcnow().isoformat(),
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"output_path": str(out_path), "filename": filename, "mime_type": "application/json", "output_format": "json"}

    # --------------------------------------------------------------------------
    # estimation helpers
    # --------------------------------------------------------------------------
    def _estimate_ocr_time(self, analysis: Dict[str, Any], opts: Dict[str, Any]) -> int:
        page_count = analysis.get("page_count", 1)
        quality = opts.get("quality", self.default_quality)
        base = 5
        mul = {"fast": 0.7, "balanced": 1.0, "accurate": 1.5}.get(quality, 1.0)
        return int(page_count * base * mul)

    def _assess_ocr_complexity(self, analysis: Dict[str, Any], opts: Dict[str, Any]) -> str:
        score = 0
        page_count = analysis.get("page_count", 1)
        iq = analysis.get("image_quality", "medium")
        quality = opts.get("quality", self.default_quality)

        if page_count > 50:
            score += 3
        elif page_count > 20:
            score += 2
        elif page_count > 10:
            score += 1

        score += {"low": 2, "medium": 0, "high": -1}.get(iq, 0)
        score += {"accurate": 1}.get(quality, 0)

        if score >= 4:
            return "high"
        if score >= 2:
            return "medium"
        return "low"

    def _estimate_ocr_accuracy(self, analysis: Dict[str, Any], opts: Dict[str, Any]) -> float:
        iq = analysis.get("image_quality", "medium")
        quality = opts.get("quality", self.default_quality)
        base = 0.8
        base += {"high": 0.1, "medium": 0.0, "low": -0.2}.get(iq, 0.0)
        base += {"accurate": 0.1, "balanced": 0.0, "fast": -0.1}.get(quality, 0.0)
        return max(0.5, min(0.95, base))

    def _get_ocr_recommendations(self, analysis: Dict[str, Any], opts: Dict[str, Any]) -> List[str]:
        rec = []
        iq = analysis.get("image_quality", "medium")
        quality = opts.get("quality", self.default_quality)
        pages = analysis.get("page_count", 1)
        potential = analysis.get("ocr_potential", "medium")

        if iq == "low" and quality == "fast":
            rec.append("Low image quality – switch to 'accurate' quality for better OCR.")
        if pages > 20 and quality == "fast":
            rec.append("Large document – use 'balanced' or 'accurate' quality.")
        if potential == "low":
            rec.append("Document already contains searchable text – OCR may be unnecessary.")
        return rec

    # --------------------------------------------------------------------------
    # DEPRECATED: Use job_operations.create_job_safely instead
    # --------------------------------------------------------------------------
    # Note: The create_ocr_job method has been removed in favor of job_operations
    # for standardized job creation across all services.
    # Use job_operations.create_job_safely(job_type='ocr', ...) instead.

    def cleanup_temp_files(self) -> None:
        """Cleanup temporary files using file management service."""
        # Delegate cleanup to file management service
        return self.file_service.cleanup_temp_files()