"""
Image Preprocessor
==================
Production image preprocessing for optimal OCR accuracy.
"""

import os
from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum
import asyncio

import structlog

logger = structlog.get_logger(__name__)

# Try to import image processing libraries
try:
    from PIL import Image, ImageFilter, ImageEnhance, ImageOps
    import numpy as np
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL/numpy not installed, preprocessing will be limited")

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV not installed, advanced preprocessing unavailable")


class PreprocessingLevel(str, Enum):
    """Preprocessing intensity levels."""
    NONE = "none"
    LIGHT = "light"  # Basic cleanup
    STANDARD = "standard"  # Recommended for most documents
    AGGRESSIVE = "aggressive"  # For poor quality scans


@dataclass
class PreprocessingConfig:
    """Configuration for image preprocessing."""
    target_dpi: int = 300
    grayscale: bool = True
    deskew: bool = True
    denoise: bool = True
    enhance_contrast: bool = True
    remove_borders: bool = True
    binarize: bool = False  # Use for very noisy documents
    binarize_threshold: int = 128


@dataclass
class PreprocessingResult:
    """Result of preprocessing operation."""
    output_path: str
    original_size: Tuple[int, int]
    processed_size: Tuple[int, int]
    original_dpi: Optional[int]
    final_dpi: int
    deskew_angle: Optional[float]
    operations_applied: list


class ImagePreprocessor:
    """
    Image preprocessing pipeline for OCR optimization.
    
    Applies:
    - DPI normalization (target 300 DPI)
    - Grayscale conversion
    - Deskewing (straightening)
    - Noise reduction
    - Contrast enhancement
    - Border removal
    """
    
    def __init__(self, config: Optional[PreprocessingConfig] = None):
        self.config = config or PreprocessingConfig()
        
        if not PIL_AVAILABLE:
            logger.warning("PIL not available, preprocessing disabled")
    
    async def preprocess(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        level: PreprocessingLevel = PreprocessingLevel.STANDARD,
    ) -> PreprocessingResult:
        """
        Preprocess an image for optimal OCR.
        
        Args:
            input_path: Path to input image
            output_path: Path for processed image (optional)
            level: Preprocessing intensity level
            
        Returns:
            PreprocessingResult with details
        """
        if not PIL_AVAILABLE:
            return PreprocessingResult(
                output_path=input_path,
                original_size=(0, 0),
                processed_size=(0, 0),
                original_dpi=None,
                final_dpi=self.config.target_dpi,
                deskew_angle=None,
                operations_applied=[]
            )
        
        # Run in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._preprocess_sync,
            input_path,
            output_path,
            level,
        )
    
    def _preprocess_sync(
        self,
        input_path: str,
        output_path: Optional[str],
        level: PreprocessingLevel,
    ) -> PreprocessingResult:
        """Synchronous preprocessing pipeline."""
        operations = []
        
        # Load image
        image = Image.open(input_path)
        original_size = image.size
        
        # Get original DPI if available
        original_dpi = None
        if "dpi" in image.info:
            original_dpi = image.info["dpi"][0]
        
        if level == PreprocessingLevel.NONE:
            # Just return original
            if output_path:
                image.save(output_path)
            return PreprocessingResult(
                output_path=output_path or input_path,
                original_size=original_size,
                processed_size=image.size,
                original_dpi=original_dpi,
                final_dpi=original_dpi or self.config.target_dpi,
                deskew_angle=None,
                operations_applied=operations
            )
        
        # 1. Convert to RGB if necessary (handle RGBA, P mode, etc.)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
            operations.append("convert_rgb")
        
        # 2. DPI normalization
        if self.config.target_dpi and original_dpi:
            if original_dpi < self.config.target_dpi:
                scale = self.config.target_dpi / original_dpi
                new_size = (int(image.width * scale), int(image.height * scale))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                operations.append(f"upscale_{self.config.target_dpi}dpi")
        
        # 3. Grayscale conversion
        if self.config.grayscale and image.mode != "L":
            image = image.convert("L")
            operations.append("grayscale")
        
        # 4. Deskew (straighten rotated documents)
        deskew_angle = None
        if self.config.deskew and CV2_AVAILABLE:
            image, deskew_angle = self._deskew_image(image)
            if deskew_angle and abs(deskew_angle) > 0.1:
                operations.append(f"deskew_{deskew_angle:.2f}deg")
        
        # 5. Denoise
        if self.config.denoise:
            if level == PreprocessingLevel.AGGRESSIVE and CV2_AVAILABLE:
                image = self._denoise_cv2(image)
                operations.append("denoise_cv2")
            else:
                image = image.filter(ImageFilter.MedianFilter(size=3))
                operations.append("denoise_median")
        
        # 6. Contrast enhancement
        if self.config.enhance_contrast:
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)
            operations.append("enhance_contrast")
        
        # 7. Sharpening for light/standard levels
        if level in (PreprocessingLevel.LIGHT, PreprocessingLevel.STANDARD):
            image = image.filter(ImageFilter.SHARPEN)
            operations.append("sharpen")
        
        # 8. Border removal (crop black borders)
        if self.config.remove_borders:
            image = self._remove_borders(image)
            operations.append("remove_borders")
        
        # 9. Binarization (for aggressive level or explicitly enabled)
        if self.config.binarize or level == PreprocessingLevel.AGGRESSIVE:
            threshold = self.config.binarize_threshold
            image = image.point(lambda x: 255 if x > threshold else 0, mode="1")
            image = image.convert("L")  # Convert back
            operations.append(f"binarize_t{threshold}")
        
        # Generate output path if not provided
        if not output_path:
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_preprocessed{ext}"
        
        # Save processed image
        image.save(output_path, dpi=(self.config.target_dpi, self.config.target_dpi))
        
        logger.info(
            "Image preprocessed",
            input=input_path,
            output=output_path,
            operations=operations
        )
        
        return PreprocessingResult(
            output_path=output_path,
            original_size=original_size,
            processed_size=image.size,
            original_dpi=original_dpi,
            final_dpi=self.config.target_dpi,
            deskew_angle=deskew_angle,
            operations_applied=operations
        )
    
    def _deskew_image(self, image: Image.Image) -> Tuple[Image.Image, Optional[float]]:
        """Detect and correct document skew using OpenCV."""
        if not CV2_AVAILABLE:
            return image, None
        
        # Convert PIL to numpy array
        img_array = np.array(image)
        
        # Detect edges
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Detect lines using Hough transform
        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)
        
        if lines is None:
            return image, 0.0
        
        # Calculate average angle
        angles = []
        for line in lines[:20]:  # Use first 20 lines
            rho, theta = line[0]
            # Convert to degrees, normalize to -45 to 45 range
            angle = (theta * 180 / np.pi) - 90
            if -45 < angle < 45:
                angles.append(angle)
        
        if not angles:
            return image, 0.0
        
        # Median angle (more robust than mean)
        deskew_angle = np.median(angles)
        
        # Only correct if angle is significant
        if abs(deskew_angle) < 0.5:
            return image, 0.0
        
        # Rotate image
        rotated = image.rotate(-deskew_angle, expand=True, fillcolor="white")
        
        return rotated, deskew_angle
    
    def _denoise_cv2(self, image: Image.Image) -> Image.Image:
        """Apply OpenCV denoising."""
        if not CV2_AVAILABLE:
            return image
        
        img_array = np.array(image)
        
        if len(img_array.shape) == 2:  # Grayscale
            denoised = cv2.fastNlMeansDenoising(img_array, None, 10, 7, 21)
        else:
            denoised = cv2.fastNlMeansDenoisingColored(img_array, None, 10, 10, 7, 21)
        
        return Image.fromarray(denoised)
    
    def _remove_borders(self, image: Image.Image) -> Image.Image:
        """Remove black/white borders from scanned documents."""
        # Auto-crop based on content
        try:
            # Invert for finding bounding box (works for white background docs)
            inverted = ImageOps.invert(image.convert("L"))
            bbox = inverted.getbbox()
            
            if bbox:
                # Add small padding
                padding = 10
                left = max(0, bbox[0] - padding)
                top = max(0, bbox[1] - padding)
                right = min(image.width, bbox[2] + padding)
                bottom = min(image.height, bbox[3] + padding)
                
                return image.crop((left, top, right, bottom))
        except Exception:
            pass
        
        return image


# Singleton instance
_preprocessor: Optional[ImagePreprocessor] = None


def get_preprocessor(config: Optional[PreprocessingConfig] = None) -> ImagePreprocessor:
    """Get or create preprocessor instance."""
    global _preprocessor
    if _preprocessor is None or config is not None:
        _preprocessor = ImagePreprocessor(config)
    return _preprocessor
