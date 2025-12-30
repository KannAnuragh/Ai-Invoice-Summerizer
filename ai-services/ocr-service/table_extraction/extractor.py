"""
Table Extraction
================
Extracts structured data from detected tables.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class TableCell:
    """A cell in an extracted table."""
    text: str
    row: int
    column: int
    row_span: int = 1
    col_span: int = 1
    is_header: bool = False
    confidence: float = 1.0


@dataclass
class ExtractedTable:
    """A fully extracted table with structured data."""
    cells: List[TableCell]
    headers: List[str]
    data: List[List[str]]  # Row-major data excluding headers
    row_count: int
    column_count: int
    confidence: float
    bounding_box: Optional[Dict[str, int]] = None


class TableExtractor:
    """
    Extract structured data from table regions.
    
    Handles:
    - Grid-based tables with visible borders
    - Borderless tables (whitespace-separated)
    - Multi-line cells
    - Merged cells
    """
    
    def __init__(
        self,
        min_columns: int = 2,
        min_rows: int = 2,
    ):
        self.min_columns = min_columns
        self.min_rows = min_rows
    
    def extract_from_region(
        self,
        image_bytes: bytes,
        region_bounds: Dict[str, int],
    ) -> Optional[ExtractedTable]:
        """
        Extract table from a specific region of the image.
        
        Args:
            image_bytes: Full document image
            region_bounds: {"x": int, "y": int, "width": int, "height": int}
            
        Returns:
            ExtractedTable or None if extraction fails
        """
        logger.info("Extracting table from region", bounds=region_bounds)
        
        # Placeholder implementation
        # In production, would use:
        # - Camelot or Tabula for PDF tables
        # - OpenCV line detection for image tables
        # - OCR with grid alignment
        
        return None
    
    def extract_from_text(
        self,
        text_blocks: List[Dict[str, Any]],
        page_width: int,
    ) -> List[ExtractedTable]:
        """
        Detect and extract tables from OCR text blocks.
        
        Uses alignment analysis to find tabular structures.
        """
        # Placeholder: Would analyze x-coordinates of text blocks
        # to identify column alignment patterns
        return []
    
    def parse_invoice_line_items(
        self,
        table: ExtractedTable,
    ) -> List[Dict[str, Any]]:
        """
        Parse an invoice line items table into structured data.
        
        Attempts to identify common columns:
        - Description
        - Quantity
        - Unit Price
        - Tax
        - Total
        """
        if not table or not table.data:
            return []
        
        # Common header patterns
        column_patterns = {
            "description": ["description", "item", "product", "service", "details"],
            "quantity": ["qty", "quantity", "units", "count"],
            "unit_price": ["unit price", "rate", "price", "unit cost"],
            "tax": ["tax", "vat", "gst", "tax amount"],
            "total": ["total", "amount", "line total", "subtotal"],
        }
        
        # Map headers to columns
        column_mapping = {}
        for i, header in enumerate(table.headers):
            header_lower = header.lower().strip()
            for field, patterns in column_patterns.items():
                if any(p in header_lower for p in patterns):
                    column_mapping[field] = i
                    break
        
        # Extract line items
        line_items = []
        for row in table.data:
            item = {}
            for field, col_idx in column_mapping.items():
                if col_idx < len(row):
                    item[field] = row[col_idx]
            if item:
                line_items.append(item)
        
        return line_items
    
    def to_dataframe_format(self, table: ExtractedTable) -> Dict[str, List]:
        """
        Convert table to column-oriented format (like pandas DataFrame).
        """
        if not table:
            return {}
        
        result = {header: [] for header in table.headers}
        
        for row in table.data:
            for i, cell in enumerate(row):
                if i < len(table.headers):
                    result[table.headers[i]].append(cell)
        
        return result


# Default extractor instance
table_extractor = TableExtractor()
