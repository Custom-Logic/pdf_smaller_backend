"""Conversion Service – Job-Oriented Architecture
Handles PDF → Word, Text, HTML, Images
Crash-hardened edition – 2025-09
"""
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.services import FileManagementService
from src.jobs import JobOperationsWrapper, JobOperations
from src.models import JobStatus

logger = logging.getLogger(__name__)

# -------------- graceful library loading ------------------------------------
try:
    import fitz  # PyMuPDF
    import pdfplumber
    PDF_LIBS_AVAILABLE = True
except ImportError:  # pragma: no cover
    PDF_LIBS_AVAILABLE = False
    logging.warning("PDF libs unavailable – install fitz & pdfplumber")

try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_AVAILABLE = True
except ImportError:  # pragma: no cover
    DOCX_AVAILABLE = False
    logging.warning("python-docx unavailable – DOCX export disabled")

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:  # pragma: no cover
    OPENPYXL_AVAILABLE = False
    logging.warning("openpyxl unavailable – Excel export disabled")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    PIL_AVAILABLE = False

    
# ------------------------------------------------------------------------------
class ConversionService:
    """Convert PDFs to docx / txt / html / images – crash-hardened."""
    def __init__(self, file_service: Optional[FileManagementService] = None):
        self.file_service = file_service or FileManagementService()
        self.supported_formats = ("docx", "txt", "html", "images", "xlsx")

    # --------------------------------------------------------------------------
    # PUBLIC ENTRY POINTS
    # --------------------------------------------------------------------------
    def convert_pdf_data(self, file_data: bytes, target_format: str, options: Optional[Dict[str, Any]] = None,
        original_filename: Optional[str] = None) -> Dict[str, Any]:
        """Convert *in-memory* PDF → target format.  Always returns the same keys."""
        options = options or {}
        if target_format not in self.supported_formats:
            raise ValueError(f"Unsupported format {target_format}")

        if not PDF_LIBS_AVAILABLE:
            raise RuntimeError("PDF libraries not installed")

        temp_pdf: Optional[Path] = None
        try:
            temp_pdf = self._save_file_data(file_data, original_filename)
            pdf_content = self._extract_pdf_content(pdf_path=temp_pdf)

            converter = {
                "docx": self._convert_to_docx,
                "txt": self._convert_to_txt,
                "html": self._convert_to_html,
                "images": lambda content, opts: self._convert_to_images_with_pdf(temp_pdf, content, opts),
                "xlsx": self._convert_to_xlsx,
            }

            _method = converter[target_format]
            # noinspection PyArgumentList
            payload = _method(content=pdf_content, opts=options)  # may raise
            # guarantee keys that callers / frontend always read
            payload.setdefault("success", True)
            payload.setdefault("format", target_format)
            payload.setdefault("quality", options.get("quality", "medium"))
            payload.setdefault("original_filename", original_filename)
            payload.setdefault("original_size", len(file_data))
            return payload

        except Exception as exc:
            logger.exception("Conversion failed")
            # always return same shape – UI will not blow up
            return {
                "success": False,
                "error": str(exc),
                "format": target_format,
                "quality": options.get("quality", "medium"),
                "original_filename": original_filename,
                "original_size": len(file_data),
            }

        finally:
            pass


    def get_conversion_preview(self, file_data: bytes, target_format: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Light-weight preview; never crashes."""
        options = options or {}
        if not PDF_LIBS_AVAILABLE:
            return self._preview_fallback(file_data, target_format, "PDF libs missing")

        temp_pdf: Optional[Path] = None
        try:
            temp_pdf = self._save_file_data(file_data, "preview.pdf")
            pdf_content = self._extract_pdf_content(temp_pdf)
            return {
                "success": True,
                "original_size": len(file_data),
                "page_count": pdf_content.get("page_count", 0),
                "estimated_size": self._estimate_output_size(pdf_content, target_format),
                "estimated_time": self._estimate_conversion_time(pdf_content, target_format),
                "complexity": self._assess_complexity(pdf_content, target_format),
                "recommendations": self._get_recommendations(pdf_content, target_format, options),
                "supported_formats": self.supported_formats,
            }
        except Exception as exc:
            logger.exception("Preview failed")
            return self._preview_fallback(file_data, target_format, str(exc))
        finally:
            if temp_pdf:
                self.file_service.delete_file(str(temp_pdf))

    # --------------------------------------------------------------------------
    # INTERNALS – extraction
    # --------------------------------------------------------------------------
    def _save_file_data(self, data: bytes, name: Optional[str] = None) -> Path:
        """Save file data using file management service"""
        filename = name or f"temp_{uuid.uuid4().hex[:8]}.pdf"
        file_id, file_path = self.file_service.save_file(data, filename)
        return Path(file_path)

    def _extract_pdf_content(self, pdf_path: Path) -> Dict[str, Any]:
        """Return unified dict with pages, tables, images, text, meta."""
        doc = fitz.open(str(pdf_path))
        content = {
            "pages": [],
            "tables": [],
            "images": [],
            "text": "",
            "page_count": len(doc),
            "metadata": doc.metadata or {},
        }
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text() or ""
            content["text"] += text + "\n"
            tables = self._extract_tables_from_page(page)
            images = self._extract_images_from_page(page)
            content["tables"].extend(tables)
            content["images"].extend(images)
            content["pages"].append(
                {
                    "page_num": page_num,
                    "text": text,
                    "tables": tables,
                    "images": images,
                    "width": page.rect.width,
                    "height": page.rect.height,
                }
            )
        doc.close()
        return content

    # --------------------------------------------------------------------------
    # TABLE / IMAGE EXTRACTION
    # --------------------------------------------------------------------------
    def _extract_tables_from_page(self, page: fitz.Page) -> List[List[List[str]]]:
        """Very small, tolerant table extractor."""
        blocks = page.get_text("dict")["blocks"]
        tables: List[List[List[str]]] = []
        for b in blocks:
            if b.get("lines") and self._looks_like_table(b):
                t = self._extract_table_data(b)
                if t:
                    tables.append(t)
        return tables

    @staticmethod
    def _looks_like_table(block: Dict[str, Any]) -> bool:
        lines = block.get("lines", [])
        if len(lines) < 2:
            return False
        span_counts = [len(ln.get("spans", [])) for ln in lines]
        return len(set(span_counts)) <= 2 and max(span_counts) > 1

    @staticmethod
    def _extract_table_data(block: Dict[str, Any]) -> Optional[List[List[str]]]:
        try:
            table: List[List[str]] = []
            for line in block["lines"]:
                row = [sp["text"].strip() for sp in line["spans"] if sp["text"].strip()]
                if row:
                    table.append(row)
            return table if table else None
        except Exception:
            return None

    @staticmethod
    def _extract_images_from_page(page: fitz.Page) -> List[Dict[str, Any]]:
        """Return image metadata (no raster extraction here)."""
        return [
            {
                "index": idx,
                "xref": img[0],
                "width": img[2],
                "height": img[3],
                "colorspace": img[4],
                "bpc": img[5],
            }
            for idx, img in enumerate(page.get_images())
        ]

    # --------------------------------------------------------------------------
    # CONVERTERS
    # --------------------------------------------------------------------------
    def _convert_to_docx(self, content: Dict[str, Any], opts: Dict[str, Any]) -> Dict[str, Any]:
        if not DOCX_AVAILABLE:
            raise RuntimeError("python-docx not installed")
        doc = Document()
        if content.get("metadata", {}).get("title"):
            title = doc.add_heading(content["metadata"]["title"], 0)
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        for page in content["pages"]:
            if page["page_num"] > 1:
                doc.add_page_break()
            # text
            if page["text"].strip():
                for para in page["text"].split("\n\n"):
                    if para.strip():
                        doc.add_paragraph(para.strip())
            # tables – ragged-row safe
            for tbl in page["tables"]:
                if not tbl:
                    continue
                max_cols = max(len(r) for r in tbl) or 1
                table = doc.add_table(rows=len(tbl), cols=max_cols)
                table.style = "Table Grid"
                for r_idx, row_data in enumerate(tbl):
                    for c_idx, cell_data in enumerate(row_data):
                        if c_idx < max_cols:
                            table.cell(r_idx, c_idx).text = str(cell_data)

        filename = f"converted_{self._secure_filename(content.get('metadata',{}).get('title') or 'document')}.docx"
        # Save to temporary location first, then read and save through file_service
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_file:
            doc.save(tmp_file.name)
            with open(tmp_file.name, 'rb') as f:
                docx_data = f.read()
            os.unlink(tmp_file.name)

        file_id, file_path = self.file_service.save_file(docx_data, filename)
        return {
            "success": True,
            "output_path": file_path,
            "filename": filename,
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "file_size": self.file_service.get_file_size(file_path),
        }

    def _convert_to_xlsx(self, content: Dict[str, Any], opts: Dict[str, Any]) -> Dict[str, Any]:
        """PDF → Excel (one worksheet per page that contains a table)."""
        if not OPENPYXL_AVAILABLE:
            raise RuntimeError("openpyxl not installed – Excel export unavailable")

        # noinspection PyUnresolvedReferences
        from openpyxl import Workbook
        # noinspection PyUnresolvedReferences
        from openpyxl.utils import get_column_letter

        wb = Workbook()
        # remove default empty sheet
        wb.remove(wb.active)

        file_prefix = self._secure_filename(content.get("metadata", {}).get("title") or "document")
        any_table = False

        for page in content["pages"]:
            if not page["tables"]:
                continue
            any_table = True
            ws = wb.create_sheet(title=f"Page_{page['page_num']}")
            for tbl_idx, tbl in enumerate(page["tables"], start=1):
                start_row = ws.max_row + (2 if ws.max_row > 1 else 0)  # blank line between tables
                for r_idx, row_data in enumerate(tbl, start=start_row):
                    for c_idx, cell_val in enumerate(row_data, start=1):
                        ws.cell(row=r_idx, column=c_idx, value=str(cell_val))

                # auto-size columns (rough)
                for c_idx in range(1, len(tbl[0]) + 1):
                    ws.column_dimensions[get_column_letter(c_idx)].auto_size = True

        if not any_table:
            # Excel file with *no* tables is useless – fail fast
            raise ValueError("No tables found in PDF – nothing to export to Excel")

        filename = f"converted_{file_prefix}.xlsx"
        # Save to temporary location first, then read and save through file_service
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            wb.save(tmp_file.name)
            with open(tmp_file.name, 'rb') as f:
                xlsx_data = f.read()
            os.unlink(tmp_file.name)

        file_id, file_path = self.file_service.save_file(xlsx_data, filename)
        return {
            "success": True,
            "output_path": file_path,
            "filename": filename,
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "file_size": self.file_service.get_file_size(file_path),
        }

    def _convert_to_txt(self, content: Dict[str, Any], opts: Dict[str, Any]) -> Dict[str, Any]:
        quality = opts.get("quality", "medium")
        text = content["text"]
        if quality != "high":
            text = re.sub(r"\s+", " ", text)
            text = re.sub(r"\n\s*\n", "\n\n", text)
        filename = f"converted_{self._secure_filename(content.get('metadata',{}).get('title') or 'document')}.txt"
        text_data = text.encode('utf-8')
        file_id, file_path = self.file_service.save_file(text_data, filename)
        return {
            "success": True,
            "output_path": file_path,
            "filename": filename,
            "mime_type": "text/plain",
            "file_size": self.file_service.get_file_size(file_path),
        }

    def _convert_to_html(self, content: Dict[str, Any], opts: Dict[str, Any]) -> Dict[str, Any]:
        html = self._generate_html_content(content, opts)
        filename = f"converted_{self._secure_filename(content.get('metadata',{}).get('title') or 'document')}.html"
        html_data = html.encode('utf-8')
        file_id, file_path = self.file_service.save_file(html_data, filename)
        return {
            "success": True,
            "output_path": file_path,
            "filename": filename,
            "mime_type": "text/html",
            "file_size": self.file_service.get_file_size(file_path),
        }

    def _convert_to_images_with_pdf(self, pdf_path: Path, content: Dict[str, Any], opts: Dict[str, Any]) -> Dict[str, Any]:
        """PDF → PNG (one file per page) using the actual PDF file."""
        if not PIL_AVAILABLE:
            raise RuntimeError("Pillow not installed – image conversion unavailable")

        dpi = {"low": 72, "medium": 150, "high": 300}.get(opts.get("quality", "medium"), 150)

        try:
            # Open the PDF document
            doc = fitz.open(str(pdf_path))
            image_files = []
            total_size = 0

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                # Get pixmap with specified DPI
                pix = page.get_pixmap(dpi=dpi)
                filename = f"converted_page_{page_num + 1}.png"

                # Convert pixmap to PNG bytes
                image_data = pix.tobytes("png")

                # Save through file service
                file_id, file_path = self.file_service.save_file(image_data, filename)
                image_files.append(file_path)
                total_size += len(image_data)

                # Clean up pixmap
                pix = None

            doc.close()

            if not image_files:
                raise RuntimeError("No images could be created")

            return {
                "success": True,
                "output_path": str(Path(image_files[0]).parent) if image_files else "",
                "filename": "pages_converted.zip",
                "mime_type": "application/zip",
                "file_size": total_size,
                "image_files": image_files,
                "page_count": len(image_files)
            }

        except Exception as e:
            logger.error(f"Image conversion failed: {e}")
            # Fall back to the text-based approach
            return self._convert_to_images(content, opts)

    def _convert_to_images(self, content: Dict[str, Any], opts: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback PDF → PNG using text rendering (when PDF file not available)."""
        if not PIL_AVAILABLE:
            raise RuntimeError("Pillow not installed – image conversion unavailable")

        dpi = {"low": 72, "medium": 150, "high": 300}.get(opts.get("quality", "medium"), 150)
        image_files = []
        total_size = 0

        # Create individual PNG files for each page using text content
        for page_data in content["pages"]:
            page_num = page_data["page_num"]
            filename = f"converted_page_{page_num}.png"

            try:
                # Create a simple text-based image representation
                from PIL import Image, ImageDraw, ImageFont

                # Create a white image
                img_width, img_height = 800, 1000
                img = Image.new('RGB', (img_width, img_height), color='white')
                draw = ImageDraw.Draw(img)

                # Try to use a basic font
                try:
                    font = ImageFont.load_default()
                except:
                    font = None

                # Draw the page text
                text = page_data.get("text", f"Page {page_num}")[:1000]  # Limit text length
                if text.strip():
                    # Simple text wrapping
                    lines = []
                    words = text.split()
                    current_line = ""

                    for word in words[:100]:  # Limit words to prevent overflow
                        if len(current_line + word) < 80:  # Rough character limit per line
                            current_line += word + " "
                        else:
                            if current_line:
                                lines.append(current_line.strip())
                            current_line = word + " "

                    if current_line:
                        lines.append(current_line.strip())

                    # Draw lines
                    y_position = 50
                    for line in lines[:40]:  # Limit lines to fit on image
                        draw.text((50, y_position), line, fill='black', font=font)
                        y_position += 25

                # Save image to bytes
                import io
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='PNG', dpi=(dpi, dpi))
                image_data = img_buffer.getvalue()
                img_buffer.close()

                file_id, file_path = self.file_service.save_file(image_data, filename)
                image_files.append(file_path)
                total_size += len(image_data)

            except Exception as e:
                logger.warning(f"Failed to create image for page {page_num}: {e}")
                # Create minimal placeholder
                placeholder_text = f"Page {page_num} - Image conversion failed"
                image_data = placeholder_text.encode('utf-8')
                file_id, file_path = self.file_service.save_file(image_data, f"page_{page_num}_error.txt")
                image_files.append(file_path)
                total_size += len(image_data)

        if not image_files:
            raise RuntimeError("No images could be created")

        return {
            "success": True,
            "output_path": str(Path(image_files[0]).parent) if image_files else "",
            "filename": "pages_converted.zip",
            "mime_type": "application/zip",
            "file_size": total_size,
            "image_files": image_files,
            "page_count": len(image_files)
        }

    # --------------------------------------------------------------------------
    # HTML generator
    # --------------------------------------------------------------------------
    def _generate_html_content(self, content: Dict[str, Any], opts: Dict[str, Any]) -> str:
        css = ""
        if opts.get("include_css", True):
            css = """
            <style>
                body{font-family:Arial,sans-serif;margin:20px}
                .page{margin-bottom:30px}
                table{border-collapse:collapse;width:100%;margin:15px 0}
                th,td{border:1px solid #ddd;padding:8px;text-align:left}
                th{background:#f2f2f2}
            </style>
            """
        parts = [
            "<!DOCTYPE html><html><head>",
            "<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
            f"<title>Converted PDF</title>{css}</head><body>",
        ]
        if content.get("metadata", {}).get("title"):
            parts.append(f"<h1>{content['metadata']['title']}</h1>")
        for page in content["pages"]:
            parts.append(f'<div class="page"><h3>Page {page["page_num"]}</h3>')
            if page["text"].strip():
                for para in page["text"].split("\n\n"):
                    if para.strip():
                        parts.append(f"<p>{para.strip()}</p>")
            for tbl in page["tables"]:
                if not tbl:
                    continue
                parts.append("<table>")
                for r_idx, row in enumerate(tbl):
                    tag = "th" if r_idx == 0 else "td"
                    parts.append("<tr>")
                    for cell in row:
                        parts.append(f"<{tag}>{cell}</{tag}>")
                    parts.append("</tr>")
                parts.append("</table>")
            parts.append("</div>")
        parts.extend(["</body></html>"])
        return "".join(parts)

    # --------------------------------------------------------------------------
    # preview helpers
    # --------------------------------------------------------------------------
    def _preview_fallback(self, file_data: bytes, fmt: str, err: str) -> Dict[str, Any]:
        return {
            "success": False,
            "error": err,
            "original_size": len(file_data),
            "page_count": 0,
            "estimated_size": 0,
            "estimated_time": 0,
            "complexity": "unknown",
            "recommendations": [],
            "supported_formats": self.supported_formats,
        }

    @staticmethod
    def _estimate_output_size(content: Dict[str, Any], fmt: str) -> int:
        base = len(content.get("text", ""))
        mul = {"docx": 1.2, "txt": 0.3, "html": 1.5, "images": 2.0}.get(fmt, 1.0)
        return int(base * mul)

    @staticmethod
    def _estimate_conversion_time(content: Dict[str, Any], fmt: str) -> int:
        pct = content.get("page_count", 1)
        tpp = {"docx": 2, "txt": 0.5, "html": 1, "images": 3}.get(fmt, 1)
        return pct * tpp

    def _assess_complexity(self, content: Dict[str, Any], _: str) -> str:
        pc, tc, ic = content.get("page_count", 0), len(content["tables"]), len(content["images"])
        if pc > 50 or tc > 20 or ic > 100:
            return "high"
        if pc > 20 or tc > 10 or ic > 50:
            return "medium"
        return "low"

    @staticmethod
    def _get_recommendations(content: Dict[str, Any], fmt: str, _: Dict[str, Any]) -> List[str]:
        rec = []
        pc, tc, ic = content.get("page_count", 0), len(content["tables"]), len(content["images"])
        if pc > 100:
            rec.append("Large document – consider splitting.")
        if tc and fmt == "txt":
            rec.append("Tables found – DOCX preserves them better.")
        if ic and fmt == "txt":
            rec.append("Images found – TXT will lose them.")
        return rec

    @staticmethod
    def _secure_filename(name: str) -> str:
        """Sanitize filename to be filesystem-safe"""
        if not name:
            return "file"
        name = re.sub(r"[^\w\s-]", "", name)
        name = re.sub(r"[-\s]+", "-", name)
        return name.strip("-") or "file"

    # --------------------------------------------------------------------------
    # JOB PROCESSING METHODS
    # --------------------------------------------------------------------------
    def process_conversion_job(self, job_id: str, file_data: bytes, target_format: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process a conversion job with provided file data and job status management
        """
        
        try:
            # Get job information
            job_info = JobOperationsWrapper.get_job_with_progress(job_id)
            if not job_info:
                raise ValueError(f"Job {job_id} not found")

            # Update job status to processing
            JobOperationsWrapper.update_job_status_safely(
                job_id=job_id,
                status=JobStatus.PROCESSING
            )

            # Get full job details for input data
            job = JobOperations.get_job(job_id=job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")

            input_data = job.input_data or {}
            original_filename = input_data.get('original_filename')
            
            # Process the file data using existing convert_pdf_data method
            result = self.convert_pdf_data(
                file_data=file_data,
                target_format=target_format,
                options=options or {},
                original_filename=original_filename
            )

            # Update job status based on result
            if result.get('success', False):
                JobOperationsWrapper.update_job_status_safely(
                    job_id=job_id,
                    status=JobStatus.COMPLETED,
                    result=result
                )
            else:
                JobOperationsWrapper.update_job_status_safely(
                    job_id=job_id,
                    status=JobStatus.FAILED,
                    error_message=result.get('error', 'Conversion failed')
                )

            return result

        except Exception as e:
            JobOperationsWrapper.update_job_status_safely(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=str(e)
            )
            logger.error(f"Error processing conversion job {job_id}: {str(e)}")
            raise

    # --------------------------------------------------------------------------
    # DEPRECATED: Use JobOperationsWrapper.create_job_safely instead
    # --------------------------------------------------------------------------
    # Note: The create_conversion_job method has been removed in favor of JobOperationsWrapper
    # for standardized job creation across all services.
    # Use JobOperationsWrapper.create_job_safely(job_type='conversion', ...) instead.