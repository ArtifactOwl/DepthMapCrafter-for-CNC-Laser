# DepthMapCrafter-for-CNC-Laser
Create a depth map (for use in laser or CNC) by selecting colors in your source image, and choosing what height these parts of the image should be.  Outputs Grayscale PNG
A visual tool for converting color images to grayscale depth/height maps,
designed for laser engraving, CNC routing, and 3D texturing workflows.

Features:
- Eyedropper color sampling from source image
- Eyedropper height sampling from depth map preview
- Single-color rules (color range → single height)
- Gradient rules (color range → height gradient for smooth transitions)
- Lasso selection with auto color range detection and flood fill
- Channel locking for flexible color matching
- Synchronized zoom and pan between views
- Live preview with histograms
- Live eyedropper preview panel
- Progress indicator for long operations
- Load existing depth maps for continued editing
- Initialize depth from brightness or uniform value
- Save/load rules to JSON for reuse across similar images
- Full resolution output
