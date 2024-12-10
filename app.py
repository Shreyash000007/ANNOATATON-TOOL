import base64
import io
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, render_template, send_file

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

def validate_and_normalize_color(color):
    """
    Validates and normalizes a given color to ensure it's within the expected range 0-1 for PyMuPDF.
    Args:
        color (list or tuple): Expected RGB color in either [0-255] or already normalized range [0-1].
    Returns:
        tuple: Normalized and clamped RGB values in the range [0, 1].
    """
    try:
        if isinstance(color, (list, tuple)) and len(color) == 3:
            # Normalize the color values if they are > 1.0
            normalized_color = tuple(float(c) / 255.0 if c > 1 else float(c) for c in color)
            # Clamp values to ensure they're strictly between 0.0 and 1.0
            return tuple(min(1.0, max(0.0, c)) for c in normalized_color)
    except:
        pass
    # Fallback to default black
    return (0.0, 0.0, 0.0)

@app.route('/save', methods=['POST'])
def save_pdf():
    data = request.get_json()
    pdf_data = base64.b64decode(data['pdf'])  # Original PDF data

    # Decode annotation data
    annotations = data.get('annotations', [])  # Expecting annotation details from frontend
    # print("Annotations => ", annotations)

    # Open the original PDF using PyMuPDF
    doc = fitz.open(stream=pdf_data, filetype="pdf")

    # Loop through the annotations and add them to the corresponding page
    for annotation in annotations:
        page_num = annotation.get("page", 1) - 1  # Get the correct page number (0-indexed)
        page = doc.load_page(page_num)  # Access the correct page

        # Ensure that annotation has required data
        if annotation["type"] == "text":
            if all(key in annotation for key in ["x1", "y1", "x2", "y2"]):
                # Add FreeText annotation (Text comment)
                rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
                text_annotation = page.add_freetext_annot(rect, annotation["text"])
                text_annotation.set_info(title=annotation.get("title", ""), subject=annotation.get("subject", ""), content=annotation.get("content", ""))
                text_annotation.update()
            else:
                print(f"Missing coordinates for text annotation: {annotation}")

        if annotation["type"] == "line":
            if all(key in annotation for key in ["x1", "y1", "x2", "y2"]):
                start = fitz.Point(annotation["x1"], annotation["y1"])
                end = fitz.Point(annotation["x2"], annotation["y2"])
                page.draw_line(start, end, color=(1, 0, 0), width=annotation.get("strokeWidth", 1))
            else:
                print(f"Missing coordinates for line annotation: {annotation}")


        elif annotation["type"] == "highlight":
            if all(key in annotation for key in ["x1", "y1", "x2", "y2"]):
                rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
                highlight_annot = page.add_highlight_annot(rect)  # Correct method for highlight
                highlight_annot.set_opacity(0.5)  # Adjust transparency
                highlight_annot.set_info(
                    title=annotation.get("title", ""),
                    subject=annotation.get("subject", "Highlight"),
                    content=annotation.get("content", "This text is highlighted.")
                )
                highlight_annot.update()
            else:
                print(f"Missing coordinates for highlight annotation: {annotation}")

        elif annotation["type"] == "underline":
            if all(key in annotation for key in ["x1", "y1", "x2", "y2"]):
                rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
                underline_annot = page.add_underline_annot(rect)  # Correct method for underline
                underline_annot.set_colors(stroke=(1, 0, 0))  # Red underline
                underline_annot.set_info(
                    title=annotation.get("title", ""),
                    subject=annotation.get("subject", "Underline"),
                    content=annotation.get("content", "This text is underlined.")
                )
                underline_annot.update()
            else:
                print(f"Missing coordinates for underline annotation: {annotation}")

        elif annotation["type"] == "strikeout":
            if all(key in annotation for key in ["x1", "y1", "x2", "y2"]):
                # Add strike-out annotation
                rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
                strikeout_annot = page.add_strikeout_annot(rect)  # Correct method for strike-out
        
                # Adjust to visually represent strike-out
                strikeout_annot.set_colors(stroke=(0, 0, 0))  # Set black color for line
                strikeout_annot.set_border(width=annotation.get("strokeWidth", 1))
                strikeout_annot.set_info(
                    title=annotation.get("title", "Strike-out"),
                    subject=annotation.get("subject", "Strike-out Annotation"),
                    content=annotation.get("content", "This text has been struck out.")
                )
                strikeout_annot.update()
            else:
                print(f"Missing coordinates for strike-out annotation: {annotation}")


        elif annotation["type"] == "square":
            if all(key in annotation for key in ["x1", "y1", "x2", "y2"]):
                # Add square annotation
                rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
                square_annot = page.add_rect_annot(rect)
                square_annot.set_info(
                    title=annotation.get("title", ""),
                    subject=annotation.get("subject", ""),
                    content=annotation.get("content", "")
                )
                
                # Validate and normalize stroke color
                default_stroke = validate_and_normalize_color(annotation.get("stroke", [0, 0, 0]))  # Normalize color
                square_annot.set_colors(stroke=default_stroke)
                square_annot.set_border(width=annotation.get("strokeWidth", 1))  # Default stroke width
                square_annot.update()
            else:
                print(f"Missing coordinates for square annotation: {annotation}")

        elif annotation["type"] == "circle":
            if all(key in annotation for key in ["x1", "y1", "radius"]):
                # Add circle annotation
                rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x1"] + annotation["radius"] * 2, annotation["y1"] + annotation["radius"] * 2)
                circle_annot = page.add_circle_annot(rect)
                circle_annot.set_info(title=annotation.get("title", ""), subject=annotation.get("subject", ""), content=annotation.get("content", ""))
                circle_annot.update()
            else:
                print(f"Missing coordinates or radius for circle annotation: {annotation}")

        elif annotation["type"] == "cloud":
            if "path" in annotation:
                # Parse the path data for the cloud
                cloud_path = annotation['path']
                points = []

                # Convert the path commands to points
                for command in cloud_path:
                    if command[0] == 'M':  # Move to
                        points.append(fitz.Point(command[1], command[2]))
                    elif command[0] == 'L':  # Line to
                        points.append(fitz.Point(command[1], command[2]))
                    elif command[0] == 'C':  # Curve to (Bézier)
                        # A cubic bezier has 3 points: current point + 2 control points
                        points.append(fitz.Point(command[1], command[2]))
                        points.append(fitz.Point(command[3], command[4]))
                        points.append(fitz.Point(command[5], command[6]))

                # Draw the polyline for the cloud
                try:
                    page.draw_polyline(
                        points,
                        color=(1, 0, 0),
                        width=annotation.get("strokeWidth", 2),
                        closePath=True  # Ensure the path is closed
                    )
                except Exception as e:
                    print(f"Error drawing cloud annotation: {e}")
            else:
                print(f"Missing path data for cloud annotation: {annotation}")

        elif annotation["type"] == "freeDraw":
            if "path" in annotation:
                # Add free draw annotation (path)
                path = annotation['path']
                fitz_path = []
                for command in path:
                    if command[0] == 'M':  # Move to
                        fitz_path.append(fitz.Point(command[1], command[2]))
                    elif command[0] == 'Q':  # Quadratic curve
                        fitz_path.append(fitz.Point(command[1], command[2]))
                        fitz_path.append(fitz.Point(command[3], command[4]))  # Curve control points

                page.draw_polyline(fitz_path, color=(0, 0, 0), width=2)  # Default color and width for free draw
                
                # Ensure valid rectangle for free text annotation
                x1, y1 = annotation.get("x1", 0), annotation.get("y1", 0)
                rect = fitz.Rect(x1, y1, x1 + 1, y1 + 1)  # Create a non-zero rect
                freeDraw_annot = page.add_freetext_annot(rect, "")
                freeDraw_annot.set_info(title=annotation.get("title", ""), subject=annotation.get("subject", ""), content=annotation.get("content", ""))
                freeDraw_annot.update()
            else:
                print(f"Missing path data for freeDraw annotation: {annotation}")

    

    # Save the annotated PDF to a byte array
    output_stream = io.BytesIO()
    doc.save(output_stream)  # Save the full document with annotations
    output_stream.seek(0)
    doc.close()
   
    # Send the annotated PDF back to the client as a downloadable file
    return send_file(output_stream, as_attachment=True, download_name="annotated.pdf", mimetype="application/pdf")

if __name__ == '__main__':
    app.run(debug=True)
