import fitz  # PyMuPDF
from fastapi import HTTPException, status
from pathlib import Path
from typing import Dict, Any

class PDFParser:
    """
    Service to validate PDF files and extract raw text from them.
    """

    @staticmethod
    def validate_pdf_signature(file_bytes: bytes) -> bool:
        """
        Validate if the file starts with the standard PDF magic signature.
        """
        return file_bytes.startswith(b"%PDF-")

    def parse_pdf(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Validates the PDF bytes and extracts text page by page.
        
        Args:
            file_bytes: The raw content of the uploaded file.
            filename: The name of the file (used for error reporting).
            
        Returns:
            A dictionary containing:
                - extracted_text (str): The compiled text.
                - character_count (int): Length of the text.
                - page_count (int): Number of pages in the PDF.
                
        Raises:
            HTTPException: If the file is not a valid PDF or is unreadable.
        """
        # Step 1: Check magic bytes signature
        if not self.validate_pdf_signature(file_bytes):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Uploaded file '{filename}' does not appear to be a valid PDF (invalid magic signature)."
            )

        # Step 2: Attempt parsing with PyMuPDF
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not open or parse the PDF file '{filename}': {str(e)}"
            )

        try:
            text_blocks = []
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_text = page.get_text()
                if page_text:
                    text_blocks.append(page_text)
            
            full_text = "\n".join(text_blocks)
            char_count = len(full_text)
            page_count = len(doc)
            
            return {
                "extracted_text": full_text,
                "character_count": char_count,
                "page_count": page_count
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred while extracting text from '{filename}': {str(e)}"
            )
        finally:
            doc.close()
