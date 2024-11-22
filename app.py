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
    # print("Annotations received:", annotations)

    # Open the original PDF using PyMuPDF
    doc = fitz.open(stream=pdf_data, filetype="pdf")

    # Loop through the annotations and add them to the corresponding page
    for annotation in annotations:
        page_num = annotation["page"] - 1  # Get the correct page number (0-indexed)
        page = doc.load_page(page_num)  # Access the correct page

        if annotation["type"] == "text":
            # Add FreeText annotation (Text comment)
            rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
            text_annotation = page.add_freetext_annot(rect, annotation["text"])
            # Set metadata to make it show in the comment pane
            text_annotation.set_info(title=annotation.get("title", ""), subject=annotation.get("subject", ""), content=annotation.get("content", ""))
            text_annotation.update()

        elif annotation["type"] == "highlight":
            # Add highlight annotation (Text comment)
            rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
            highlight_annot = page.add_highlight_annot(rect)
            # Set metadata to make it show in the comment pane
            highlight_annot.set_info(title=annotation.get("title", ""), subject=annotation.get("subject", ""), content=annotation.get("content", ""))
            highlight_annot.update()

        elif annotation["type"] == "circle":
            # Add circle annotation
            rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x1"] + annotation["radius"] * 2,
                             annotation["y1"] + annotation["radius"] * 2)
            circle_annot = page.add_circle_annot(rect)
            # Set metadata to make it show in the comment pane
            circle_annot.set_info(title=annotation.get("title", ""), subject=annotation.get("subject", ""), content=annotation.get("content", ""))
            circle_annot.update()

        elif annotation["type"] == "line":
            # Add line annotation (Text comment)
            line_start = fitz.Point(annotation["x1"], annotation["y1"])
            line_end = fitz.Point(annotation["x2"], annotation["y2"])
            line_annot = page.add_line_annot(line_start, line_end)
            # Set metadata to make it show in the comment pane
            line_annot.set_info(title=annotation.get("title", ""), subject=annotation.get("subject", ""), content=annotation.get("content", ""))
            line_annot.update()

    # Save the annotated PDF to a byte array
    output_stream = io.BytesIO()
    doc.save(output_stream)  # Save the full document with annotations
    output_stream.seek(0)
    doc.close()

    # Send the annotated PDF back to the client as a downloadable file
    return send_file(output_stream, as_attachment=True, download_name="annotated.pdf", mimetype="application/pdf")

if __name__ == '__main__':
    app.run(debug=True)
