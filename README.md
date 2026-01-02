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


Requirements:
You will need Python installed (above 11.0 should work fine) on Windows, Mac, or Linux
You need to install Pillow in Python:
**pip install Pillow**



The tool allows you to select certain colors and apply a certain depth value to all pixels of that color (with selectable tolerance) over the whole image.  Or, you can use eyedropper tool two colors, creating a color range.  Then select two grayscale values to represent the corresponding depth range, and it will then apply that depth range to the color range you have chosen.

Finally, instead of just applying the depth to all pixels globally, you can select a bounded region with a lasso tool, and then you replace the color range inside that lasso with the high and low values that you have chosen for depth.  You can also allow it to spread outside to neighboring pixels of a similar shade by doing a flood fill.

