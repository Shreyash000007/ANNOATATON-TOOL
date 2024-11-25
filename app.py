import base64
import io
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, render_template, send_file

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/save', methods=['POST'])
def save_pdf():
    data = request.get_json()
    pdf_data = base64.b64decode(data['pdf'])  # Original PDF data

    # Decode annotation data
    annotations = data.get('annotations', [])  # Expecting annotation details from frontend
    print("Annotations => ", annotations)

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

        elif annotation["type"] == "highlight":
            if all(key in annotation for key in ["x1", "y1", "x2", "y2"]):
                # Add highlight annotation
                rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
                highlight_annot = page.add_highlight_annot(rect)
                highlight_annot.set_info(title=annotation.get("title", ""), subject=annotation.get("subject", ""), content=annotation.get("content", ""))
                highlight_annot.update()
            else:
                print(f"Missing coordinates for highlight annotation: {annotation}")

        elif annotation["type"] == "circle":
            if all(key in annotation for key in ["x1", "y1", "radius"]):
                # Add circle annotation
                rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x1"] + annotation["radius"] * 2, annotation["y1"] + annotation["radius"] * 2)
                circle_annot = page.add_circle_annot(rect)
                circle_annot.set_info(title=annotation.get("title", ""), subject=annotation.get("subject", ""), content=annotation.get("content", ""))
                circle_annot.update()
            else:
                print(f"Missing coordinates or radius for circle annotation: {annotation}")

        elif annotation["type"] == "line":
            if all(key in annotation for key in ["x1", "y1", "x2", "y2"]):
                # Add line annotation
                line_start = fitz.Point(annotation["x1"], annotation["y1"])
                line_end = fitz.Point(annotation["x2"], annotation["y2"])
                line_annot = page.add_line_annot(line_start, line_end)
                line_annot.set_info(title=annotation.get("title", ""), subject=annotation.get("subject", ""), content=annotation.get("content", ""))
                line_annot.update()
            else:
                print(f"Missing coordinates for line annotation: {annotation}")

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
                        fitz_path.append(fitz.Point(command[3], command[4]))

                page.draw_polyline(fitz_path, color=(0, 0, 0), width=2)
                rect = fitz.Rect(annotation.get("x1", 0), annotation.get("y1", 0), annotation.get("x1", 0) + 1, annotation.get("y1", 0) + 1)
                freeDraw_annot = page.add_freetext_annot(rect, "")
                freeDraw_annot.set_info(title=annotation.get("title", ""), subject=annotation.get("subject", ""), content=annotation.get("content", ""))
                freeDraw_annot.update()
            else:
                print(f"Missing path data for freeDraw annotation: {annotation}")

        elif annotation["type"] == "cloud":
            if "path" in annotation:
                # Cloud annotation - Ensure 'path' is a series of move (M) and curve (C) commands
                path = annotation["path"]
                fitz_path = []
                for command in path:
                    if command[0] == 'M':  # Move to
                        fitz_path.append(fitz.Point(command[1], command[2]))
                    elif command[0] == 'C':  # Cubic Bezier curve
                        fitz_path.append(fitz.Point(command[1], command[2]))
                        fitz_path.append(fitz.Point(command[3], command[4]))
                        fitz_path.append(fitz.Point(command[5], command[6]))

                # Draw the cloud-shaped path using draw_polygon (for closed shapes)
                page.draw_polygon(fitz_path, color=(0, 0, 0), width=2, fill=(0.9, 0.9, 0.9))  # Adjust color and width as needed

                # Optionally, you can add a text annotation inside the cloud shape
                rect = fitz.Rect(annotation.get("x1", 0), annotation.get("y1", 0), annotation.get("x2", 0), annotation.get("y2", 0))
                cloud_annot = page.add_freetext_annot(rect, annotation.get("text", ""))
                cloud_annot.set_info(title=annotation.get("title", ""), subject=annotation.get("subject", ""), content=annotation.get("content", ""))
                cloud_annot.update()
            else:
                print(f"Missing path data for cloud annotation: {annotation}")

    # Save the annotated PDF to a byte array
    output_stream = io.BytesIO()
    doc.save(output_stream)  # Save the full document with annotations
    output_stream.seek(0)
    doc.close()

    # Send the annotated PDF back to the client as a downloadable file
    return send_file(output_stream, as_attachment=True, download_name="annotated.pdf", mimetype="application/pdf")

if __name__ == '__main__':
    app.run(debug=True)
