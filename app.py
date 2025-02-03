import base64
import io
import fitz  
import os
from flask import Flask, request, jsonify, render_template, send_file, send_from_directory
import pyodbc 
from datetime import datetime
import json

app = Flask(__name__)

DB_CONFIG = {
    'SERVER': 'DESKTOP-EHPE93D\\SQLEXPRESS',
    'DATABASE': 'PDFAnnotations',
    'TRUSTED_CONNECTION': 'yes'
}

def get_db_connection():
    conn_str = (
        f"DRIVER={{SQL Server}};"
        f"SERVER={DB_CONFIG['SERVER']};"
        f"DATABASE={DB_CONFIG['DATABASE']};"
        f"Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/images/<filename>')
def serve_image(filename):
    image_directory = 'C:/Users/PC/Downloads/Pdf Annotation/PDF_22_12_24/PDF_22_12_24/PDF_18_12_24/PDF/images'  # Path to your image directory
    print(f"Serving image: {filename}")
    return send_from_directory(image_directory, filename)

@app.route('/assets/<path:path>')
def send_assets(path):
    return send_from_directory('assets',path)

def validate_and_normalize_color(color):
    try:
        if isinstance(color, (list, tuple)) and len(color) == 3:
            normalized_color = tuple(float(c) / 255.0 if c > 1 else float(c) for c in color)
            return tuple(min(1.0, max(0.0, c)) for c in normalized_color)
    except Exception as e:
        print(f"Error normalizing color: {e}")
    return (0.0, 0.0, 0.0)

@app.route('/save', methods=['POST'])
def save_pdf():
    try:
        data = request.get_json()
        pdf_data = base64.b64decode(data['pdf'])
        annotations = data.get('annotations', [])

        # Create annotated PDF as before
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        # Process annotations as in your existing code
        for annotation in annotations:
            try:
                page_num = annotation.get("page", 1) - 1
                page = doc.load_page(page_num)

                if annotation["type"] == "text":
                    if all(key in annotation for key in ["x1", "y1", "x2", "y2", "text"]):
                        rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
                        text_annotation = page.add_freetext_annot(rect, annotation["text"])
                        
                        # Set text appearance properties
                        text_annotation.set_colors(stroke=(0, 0, 0), fill=(1, 1, 1))  # Black text, white background
                        # text_annotation.update(fontsize=annotation.get("fontSize", 12),  # Set font size
                                            # text_color=(0, 0, 0),  # Black text
                                            # border_color=(0, 0, 0),  # Black border
                                            # fill_color=(1, 1, 1))  # White background
                        
                        # Set text alignment and font
                        text_annotation.set_info(
                            title=annotation.get("title", "Text Annotation"),
                            subject=annotation.get("subject", "Text"),
                            content=annotation.get("content", annotation["text"])
                        )
                        
                        # Ensure the text is visible and properly formatted
                        text_annotation.set_border(width=0.5)  # Add a slight border
                        text_annotation.update()
                        
                        # Draw the text directly on the page as a backup
                        page.insert_text(
                            point=fitz.Point(annotation["x1"], annotation["y1"] + 12),  # Adjust Y for baseline
                            text=annotation["text"],
                            # fontsize=annotation.get("fontSize", 12),
                            # color=(0, 0, 0)  # Black color
                        )
                    else:
                        print(f"Missing coordinates or text for text annotation: {annotation}")

                elif annotation["type"] == "line":
                    if all(key in annotation for key in ["x1", "y1", "x2", "y2"]):
                        start = fitz.Point(annotation["x1"], annotation["y1"])
                        end = fitz.Point(annotation["x2"], annotation["y2"])

                        # Create a line annotation instead of just drawing the line
                        line_annot = page.add_line_annot(start, end)

                        # Set additional metadata for the annotation
                        line_annot.set_info(
                            title=annotation.get("title", ""),
                            subject=annotation.get("subject", ""),
                            content=annotation.get("content", "")
                        )

                       # Set line properties
                        line_annot.set_colors(stroke=(1, 0, 0))  # Red color
                        line_annot.set_border(width=annotation.get("strokeWidth", 1))

                        # Finalize the annotation
                        line_annot.update()
                    else:
                        print(f"Missing coordinates for line annotation: {annotation}")

                elif annotation["type"] == "highlight":
                    if "x1" in annotation and "y1" in annotation and "x2" in annotation and "y2" in annotation:
                        rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
                        highlight_annot = page.add_highlight_annot(rect)
                        highlight_annot.set_opacity(0.5)
                        highlight_annot.set_info(
                            title=annotation.get("title", ""),
                            subject=annotation.get("subject", "Highlight"),
                            content=annotation.get("content", "This text is highlighted.")
                        )
                        highlight_annot.update()
                    elif "relativeRect" in annotation and "text" in annotation:
                        rect_data = annotation["relativeRect"]
                        rect = fitz.Rect(
                            rect_data["left"], rect_data["top"],
                            rect_data["left"] + rect_data["width"],
                            rect_data["top"] + rect_data["height"]
                        )
                        highlight_annot = page.add_highlight_annot(rect)
                        highlight_annot.set_opacity(0.5)
                        highlight_annot.set_info(
                            title=annotation.get("title", ""),
                            subject=annotation.get("subject", "Highlight"),
                            content=annotation.get("content", "This text is highlighted.")
                        )
                        highlight_annot.update()
                        
                    elif "lineAnnotations" in annotation:
                        # List to hold individual bounding boxes for line annotations
                        rects = []

                        # Iterate through all line annotations and create bounding boxes for each one
                        for line in annotation["lineAnnotations"]:
                            if "left" in line and "top" in line and "width" in line and "height" in line:
                                # Create a bounding box for the current line annotation
                                rect = fitz.Rect(line["left"], line["top"], line["left"] + line["width"], line["top"] + line["height"])
                                rects.append(rect)  # Add the rect to the list
                            else:
                                print(f"Missing coordinates for line annotation: {line}")

                        # If we have valid bounding boxes, create highlight annotations
                        if rects:
                            for rect in rects:
                                if rect.width > 0 and rect.height > 0:
                                    highlight_annot = page.add_highlight_annot(rect)
                                    highlight_annot.set_opacity(0.5)
                                    highlight_annot.set_info(
                                        title=annotation.get("title", ""),
                                        subject=annotation.get("subject", "Highlight"),
                                        content=annotation.get("content", "This text is highlighted.")
                                    )
                                    highlight_annot.update()
                            # print(f"Highlight annotation: Title: {annotation.get('title', '')}, Subject: {annotation.get('subject', 'Highlight')}, Content: {annotation.get('content', 'This text is highlighted.')}, Coordinates: {annotation['x1']}, {annotation['y1']} to {annotation['x2']}, {annotation['y2']}")
                        else:
                            print("No valid line annotations found.")


                
                    else:
                        print(f"Missing coordinates for highlight annotation: {annotation} (Check if 'relativeRect' or 'text' is missing)")


                elif annotation["type"] == "underline":
                    if "x1" in annotation and "y1" in annotation and "x2" in annotation and "y2" in annotation:
                        # Case with explicit coordinates
                        rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
                        underline_annot = page.add_underline_annot(rect)
                        underline_annot.set_colors(stroke=(1, 0, 0))  # Optional: red color for underline
                        underline_annot.set_info(
                            title=annotation.get("title", ""),
                            subject=annotation.get("subject", "Underline"),
                            content=annotation.get("content", "This text is underlined.")
                        )
                        underline_annot.update()
                    elif "relativeRect" in annotation and "text" in annotation:
                        # Case with relativeRect
                        rect_data = annotation["relativeRect"]
                        rect = fitz.Rect(
                            rect_data["left"], rect_data["top"],
                            rect_data["left"] + rect_data["width"],
                            rect_data["top"] + rect_data["height"]
                        )
                        underline_annot = page.add_underline_annot(rect)
                        underline_annot.set_colors(stroke=(1, 0, 0))  # Set color to red
                        # underline_annot.set_text(annotation["text"])
                        underline_annot.set_info(
                            title=annotation.get("title", ""),
                            subject=annotation.get("subject", "Underline"),
                            content=annotation.get("content", "This text is underlined.")
                        )
                        underline_annot.update()
                    elif annotation["type"] == "underline":
                        if "lineAnnotations" in annotation:
                            for line in annotation["lineAnnotations"]:
                                if "left" in line and "top" in line and "width" in line and "height" in line:
                                    rect = fitz.Rect(
                                        line["left"],
                                        line["top"],
                                        line["left"] + line["width"],
                                        line["top"] + line["height"]
                                    )
                                    if rect.width > 0 and rect.height > 0:
                                        underline_annot = page.add_underline_annot(rect)
                                        underline_annot.set_colors(stroke=(1, 0, 0))  # Optional: red color for underline
                                        underline_annot.set_info(
                                            title=annotation.get("title", ""),
                                            subject=annotation.get("subject", "Underline"),
                                            content=annotation.get("content", "This text is underlined.")
                                        )
                                        underline_annot.update()
                    
                                else:
                                    print(f"Missing coordinates for line annotation: {line}")                      
                        else:
                            print(f"Missing line annotations for underline annotation: {annotation}")

                elif annotation["type"] == "strikeout":
                    if all(key in annotation for key in ["x1", "y1", "x2", "y2"]):
                        rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
                        strikeout_annot = page.add_strikeout_annot(rect)
                        strikeout_annot.set_colors(stroke=(1, 0, 0))
                        strikeout_annot.set_border(width=annotation.get("strokeWidth", 1))
                        strikeout_annot.set_info(
                            title=annotation.get("title", "Strike-out"),
                            subject=annotation.get("subject", "Strike-out Annotation"),
                            content=annotation.get("content", "This text has been struck out.")
                        )
                        strikeout_annot.update()
                    elif "relativeRect" in annotation and "text" in annotation:
                        rect_data = annotation["relativeRect"]
                        rect = fitz.Rect(
                            rect_data["left"], rect_data["top"],
                            rect_data["left"] + rect_data["width"],
                            rect_data["top"] + rect_data["height"]
                        )
                        # y_mid = rect.top + (rect.height / 2)
                        strikeout_annot = page.add_strikeout_annot(rect)
                        strikeout_annot.set_colors(stroke=(1, 0, 0))  # Red color for strikeout
                        strikeout_annot.set_border(width=annotation.get("strokeWidth", 1))
                        strikeout_annot.set_info(
                            title=annotation.get("title", "Strike-out"),
                            subject=annotation.get("subject", "Strike-out Annotation"),
                            content=annotation.get("content", "This text has been struck out.")
                        )
                        strikeout_annot.update()
                    elif annotation["type"] == "strikeout":
                        if "lineAnnotations" in annotation:
                            for line in annotation["lineAnnotations"]:
                                if "left" in line and "top" in line and "width" in line and "height" in line:
                                    rect = fitz.Rect(
                                        line["left"],
                                        (line["top"])-8,
                                        line["left"] + line["width"],
                                        line["top"] + line["height"]
                                    )
                                    if rect.width > 0 and rect.height > 0:
                                        strikeout_annot = page.add_strikeout_annot(rect)
                                        strikeout_annot.set_colors(stroke=(1, 0, 0))  # Optional: red color for strikeout
                                        # strikeout_annot.set_border(dashes=0, width=1)  # Set stroke width
                                        strikeout_annot.set_border(width=annotation.get("strokeWidth", 1))

                                        strikeout_annot.set_info(
                                            title=annotation.get("title", ""),
                                            subject=annotation.get("subject", "Strikeout"),
                                            content=annotation.get("content", "This text is struck out.")
                                        )
                                        strikeout_annot.update()
                                        print(annotation)
                                else:
                                    print(f"Missing coordinates for line annotation: {line}")
                    else:
                        print(f"Missing coordinates for strike-out annotation: {annotation}")
                    
                elif annotation["type"] == "stamp":
                    img_src = annotation.get("imgSrc")
                    x1 = annotation.get("x1")
                    y1 = annotation.get("y1")
                    x2 = annotation.get("x2")
                    y2 = annotation.get("y2")

                    if img_src and x1 is not None and y1 is not None and x2 is not None and y2 is not None:
                        width = x2 - x1
                        height = y2 - y1

                        img_path = os.path.join(os.getcwd(), img_src.lstrip('/'))  # Get the absolute path
                        if os.path.exists(img_path):
                            # Read the image as a byte stream
                            with open(img_path, "rb") as img_file:
                                img_data = img_file.read()
                            
                            # Use fitz to open the image as a stream
                            img_rect = fitz.Rect(x1-300, y1-70, x2-50, y2-70)  # Define the rectangle area for the stamp
                            page.insert_image(img_rect, stream=img_data, width=width, height=height)

                        # Optionally, add metadata for the stamp annotation
                        stamp_annot = page.add_text_annot(fitz.Rect(x1, y1, x2, y2), '')
                        stamp_annot.set_info(
                            title=annotation.get("title", "Stamp Annotation"),
                            subject=annotation.get("subject", "Stamp Subject"),
                            content=annotation.get("content", "This is a stamp annotation")
                        )
                        stamp_annot.update()

                elif annotation["type"] == "signature":
                    img_data = annotation.get("dataURL")  # Base64-encoded image data
                    x1, y1 = annotation.get("x1"), annotation.get("y1")
                    x2, y2 = annotation.get("x2"), annotation.get("y2")

                    # Validate essential fields
                    if not img_data:
                        print(f"Missing image data for signature annotation: {annotation}")
                        continue
                    if any(coord is None for coord in [x1, y1, x2, y2]):
                        print(f"Invalid coordinates for signature annotation: {annotation}")
                        continue

                    try:
                        # Decode base64 image data
                        if "," in img_data:
                            img_bytes = base64.b64decode(img_data.split(",")[1])
                        else:
                            img_bytes = base64.b64decode(img_data)

                        # Validate image dimensions
                        width = x2 - x1
                        height = y2 - y1
                        if width <= 0 or height <= 0:
                            print(f"Invalid dimensions for signature annotation: {annotation}")
                            continue

                        # Create a rectangle for the image
                        img_rect = fitz.Rect(x1-400, y1-80, x2, y2-80)

                        # Insert the image into the PDF
                        page.insert_image(img_rect, stream=io.BytesIO(img_bytes))
                        sig_annot = page.add_text_annot(fitz.Rect(x1, y1, x2, y2), '')
                        sig_annot.set_info(
                            title=annotation.get("title", "Signature Annotation"),
                            subject=annotation.get("subject", "Signature Subject"),
                            content=annotation.get("content", "This is a signature annotation")
                        )
                        sig_annot.update()
                        print(f"Signature annotation successfully added at page {annotation.get('page')}, coordinates: ({x1}, {y1}), ({x2}, {y2})")

                    except Exception as e:
                        print(f"Error adding signature annotation: {e}, annotation: {annotation}")


                elif annotation["type"] == "square":
                    if all(key in annotation for key in ["x1", "y1", "x2", "y2"]):
                        rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
                        square_annot = page.add_rect_annot(rect)
                        square_annot.set_info(
                            title=annotation.get("title", ""),
                            subject=annotation.get("subject", ""),
                            content=annotation.get("content", "")
                        )
                        square_annot.set_colors(stroke=[1, 0, 0])  # Red in RGB format
                        square_annot.set_border(width=annotation.get("strokeWidth", 1))
                        square_annot.update()
                        # print(f"Added square annotation: {annotation}")
                    else:
                        print(f"Missing coordinates for square annotation: {annotation}")

                elif annotation["type"] == "circle":
                    if all(key in annotation for key in ["x1", "y1", "radius"]):
                        radius = annotation["radius"]
                        if radius > 0:
                            rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x1"] + radius * 2, annotation["y1"] + radius * 2)
                            circle_annot = page.add_circle_annot(rect)
                            circle_annot.set_info(
                                title=annotation.get("title", ""),
                                subject=annotation.get("subject", ""),
                                content=annotation.get("content", "")
                            )
                            circle_annot.set_border(width=2)  # Set stroke width to 2

                            circle_annot.update()
                        else:
                            print(f"Invalid radius for circle annotation: {annotation}")
                    else:
                        print(f"Missing data for circle annotation: {annotation}")

                elif annotation["type"] == "cloud":
                    if "path" in annotation and isinstance(annotation["path"], list):
                        cloud_path = annotation['path']
                        points = []
                        for command in cloud_path:
                            if command[0] == 'M':
                                points.append(fitz.Point(command[1], command[2]))
                            elif command[0] == 'L':
                                points.append(fitz.Point(command[1], command[2]))
                            elif command[0] == 'C':
                                points.append(fitz.Point(command[1], command[2]))
                                points.append(fitz.Point(command[3], command[4]))
                                points.append(fitz.Point(command[5], command[6]))
                        try:
                            cloud_annot = page.add_polyline_annot(points)
                            cloud_annot.set_info(
                                title=annotation.get("title", "Cloud Annotation"),
                                subject=annotation.get("subject", "Cloud"),
                                content=annotation.get("content", "")
                           )
                            page.draw_polyline(
                                points,
                                color=(1, 0, 0),
                                width=annotation.get("strokeWidth", 2),
                                closePath=True
                            )
                        except Exception as e:
                            print(f"Error drawing cloud annotation: {e}")
                    else:
                        print(f"Missing path data for cloud annotation: {annotation}")

                elif annotation["type"] == "freeDraw":
                    if "path" in annotation:
                        path = annotation["path"]
                        fitz_path = []

                        for command in path:
                            if command[0] == 'M':  # Move to
                                fitz_path.append(fitz.Point(command[1], command[2]))
                            elif command[0] == 'Q':  # Quadratic curve
                                fitz_path.append(fitz.Point(command[1], command[2]))
                                fitz_path.append(fitz.Point(command[3], command[4]))

                        # Create a polyline annotation for FreeDraw
                        free_draw_annot = page.add_polyline_annot(fitz_path)

                        # Set metadata for the annotation
                        free_draw_annot.set_info(
                           title=annotation.get("title", ""),
                            subject=annotation.get("subject", ""),
                            content=annotation.get("content", "")
                        )

                        # Set appearance properties
                        free_draw_annot.set_colors(stroke=(1, 0, 0))  # Red color
                        free_draw_annot.set_border(width=annotation.get("strokeWidth", 2))

                        # Finalize the annotation
                        free_draw_annot.update()
                    else:
                        print(f"Missing path data for freeDraw annotation: {annotation}")

              
            except Exception as e:
                print(f"Error processing annotation {annotation}: {e}")

        output_stream = io.BytesIO()
        doc.save(output_stream)
        annotated_pdf = output_stream.getvalue()
        doc.close()

        # Store in database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Modified INSERT query to handle SCOPE_IDENTITY()
        cursor.execute("""
            INSERT INTO PDFDocuments (FileName, OriginalPDF, AnnotatedPDF, UploadDate, LastModifiedDate)
            OUTPUT INSERTED.DocumentID
            VALUES (?, ?, ?, GETDATE(), GETDATE())
        """, (
            'document.pdf',  # Default filename since we're not using file upload
            pdf_data,
            annotated_pdf
        ))
        
        # Get the inserted document ID
        row = cursor.fetchone()
        document_id = row[0] if row else None

        if document_id:
            # Insert annotations
            for annotation in annotations:
                cursor.execute("""
                    INSERT INTO Annotations (DocumentID, AnnotationType, PageNumber, AnnotationData, CreatedDate, ModifiedDate)
                    VALUES (?, ?, ?, ?, GETDATE(), GETDATE())
                """, (
                    document_id,
                    annotation['type'],
                    annotation.get('page', 1),
                    json.dumps(annotation)
                ))

        conn.commit()
        conn.close()

        # Return the annotated PDF
        output_stream.seek(0)
        return send_file(
            output_stream,
            as_attachment=True,
            download_name="annotated.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:
        print(f"Error in save_pdf: {e}")
        return jsonify({"error": str(e)}), 500

# Add new routes for retrieving PDFs and annotations

@app.route('/documents', methods=['GET'])
def get_documents():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT DocumentID, FileName, UploadDate FROM PDFDocuments ORDER BY UploadDate DESC")
        documents = [{"id": row[0], "filename": row[1], "upload_date": row[2]} for row in cursor.fetchall()]
        
        conn.close()
        return jsonify(documents)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/document/<int:document_id>', methods=['GET'])
def get_document(document_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT AnnotatedPDF FROM PDFDocuments WHERE DocumentID = ?", (document_id,))
        result = cursor.fetchone()
        
        if result:
            pdf_data = result[0]
            return send_file(
                io.BytesIO(pdf_data),
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f"document_{document_id}.pdf"
            )
        else:
            return jsonify({"error": "Document not found"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/annotations/<int:document_id>', methods=['GET'])
def get_annotations(document_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT AnnotationType, PageNumber, AnnotationData 
            FROM Annotations 
            WHERE DocumentID = ? 
            ORDER BY PageNumber, CreatedDate
        """, (document_id,))
        
        annotations = [
            {
                "type": row[0],
                "page": row[1],
                "data": json.loads(row[2])
            }
            for row in cursor.fetchall()
        ]
        
        conn.close()
        return jsonify(annotations)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
