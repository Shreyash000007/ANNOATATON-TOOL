import base64
import io
import uuid
import fitz  
import os
from flask import Flask, request, jsonify, render_template, send_file, send_from_directory,Response
import pyodbc 
from datetime import datetime
import json
from urllib.parse import unquote
from flask_cors import CORS
from flask import Flask, request, jsonify, make_response
from requests.exceptions import RequestException
import urllib3
import requests
import sys
import logging
from logging.handlers import RotatingFileHandler
from urllib.parse import unquote, urlparse
from werkzeug.utils import secure_filename
import traceback
import tempfile



sys.path.append(os.path.dirname(__file__))



urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


app = Flask(__name__)
CORS(app)



@app.route('/test')
def test():
    logger.info('Test route accessed')
    return 'Test route works!'

logging.basicConfig(
    filename='D:\\Publish Site\\error.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS, DELETE"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

@app.route('/api/comment/Pdf', methods=['OPTIONS'])
def handle_options():
    response = jsonify({'status': 'ok'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
    return response

@app.route('/proxy/annotation', methods=['POST'])
def proxy_annotation():
    try:
        data = request.get_json()
        
        response = requests.post(
            'http://idmsdemo.vishwatechnologies.com/api/comment/PdfAnnotation',
            json=data,  # Send as JSON
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            verify=False,
            timeout=10 
        )
        
        return jsonify(response.json()), response.status_code
        
    except requests.exceptions.RequestException as e:
        print(f"Error forwarding request: {str(e)}")
        return jsonify({
            "error": "Failed to reach annotation server",
            "details": str(e)
        }), 502


DB_CONFIG = {
    'DRIVER': '{SQL Server}',
    'SERVER': 'DESKTOP-EHPE93D\\SQLEXPRESS',
    'DATABASE': 'PDFAnnotations',
    'TRUSTED_CONNECTION': 'yes'
}

# For IIS 

def get_db_connection():
    try:
        conn_str = (
            f"DRIVER={{SQL Server}};"
            f"SERVER={DB_CONFIG['SERVER']};"
            f"DATABASE={DB_CONFIG['DATABASE']};"
            f"Trusted_Connection=yes;"
        )
        return pyodbc.connect(conn_str)
    except pyodbc.Error as e:
        print(f"Database connection error: {str(e)}")
        raise Exception(f"Database connection failed: {str(e)}")

# For Local Server App.py

# def get_db_connection():
#     conn_str = (
#         f"DRIVER={{SQL Server}};"
#         f"SERVER={DB_CONFIG['SERVER']};"
#         f"DATABASE={DB_CONFIG['DATABASE']};"
#         f"Trusted_Connection=yes;"
#     )
#     return pyodbc.connect(conn_str)

@app.route('/api/comment/Pdf', methods=['POST'])
def save_pdf_annotation():
    try:
        print("Received request")
        
        if 'file' not in request.files:
            print("No file in request")
            return jsonify({"error": "No file part"}), 400
            
        file = request.files['file']
        DocumentId = request.form.get('DocumentId')
        annotations_json = request.form.get('annotations')

        if not DocumentId:
            print("No DocumentId provided")
            return jsonify({"error": "No DocumentId provided"}), 400

        if not annotations_json:
            print("No annotations provided")
            return jsonify({"error": "No annotations provided"}), 400

        
        print(f"DocumentId: {DocumentId}")
        print(f"File name: {file.filename}")
        
        annotations = json.loads(annotations_json)
        print(f"Processing {len(annotations)} annotations")

        pdf_bytes = file.read()
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")

        for annotation in annotations:
            try:
                page_num = int(annotation.get("page", 1))
                if page_num <= 0:
                    page_num = 1
                page = pdf_document[page_num - 1]  # Convert to 0-based index
                
                print(f"Processing annotation type: {annotation['type']} on page {page_num}")

                if annotation["type"] == "text":
                    if all(key in annotation for key in ["x1", "y1", "x2", "y2", "text"]):
                        rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
                        text_annotation = page.add_freetext_annot(rect, annotation["text"])
                        
                        text_annotation.set_colors(stroke=(0, 0, 0), fill=(1, 1, 1))  # Black text, white background
                        # text_annotation.update(fontsize=annotation.get("fontSize", 12),  # Set font size
                                            # text_color=(0, 0, 0),  # Black text
                                            # border_color=(0, 0, 0),  # Black border
                                            # fill_color=(1, 1, 1))  # White background
                        
                        text_annotation.set_info(
                            title=annotation.get("userName", "Anurag Sable"),
                            subject=annotation.get("subject", "Text"),
                            content=annotation.get("content", annotation["text"])
                        )
                        
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
                            
                            title=annotation.get("userName", "Anurag Sable"),
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
                            title=annotation.get("userName", "Anurag Sable"),
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
                            title=annotation.get("userName", "Anurag Sable"),
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
                                        title=annotation.get("userName", "Anurag Sable"),
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
                            title=annotation.get("userName", "Anurag Sable"),
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
                            title=annotation.get("userName", "Anurag Sable"),
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
                                            title=annotation.get("userName", "Anurag Sable"),
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
                            title=annotation.get("userName", "Anurag Sable"),
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
                            title=annotation.get("userName", "Anurag Sable"),
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
                                            title=annotation.get("userName", "Anurag Sable"),
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
                            title=annotation.get("userName", "Anurag Sable"),
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
                            title=annotation.get("userName", "Anurag Sable"),
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
                            # title=annotation.get("title", ""),
                            title=annotation.get("userName", "Anurag Sable"),
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
                                title=annotation.get("userName", "Anurag Sable"),
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
                                title=annotation.get("userName", "Anurag Sable"),
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
                           title=annotation.get("userName", "Anurag Sable"),
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
                print(f"Error processing annotation: {e}")
                continue
                

            
        output_buffer = io.BytesIO()
        pdf_document.save(output_buffer)
        pdf_document.close()
        output_buffer.seek(0)
        
        files = {
            'file': ('annotated.pdf', output_buffer, 'application/pdf')
        }
        data = {
            'DocumentId': DocumentId
        }
        
        # Send to external API
        print("Sending request to external API")
        response = requests.post(
            'http://idmsdemo.vishwatechnologies.com/api/comment/Pdf',
            files=files,
            data=data,
            verify=False
        )
        
        print(f"External API response status: {response.status_code}")
        print(f"External API response: {response.text}")
        
        # Return the response from the external API
        return Response(
            response.content,
            status=response.status_code,
            mimetype=response.headers.get('content-type', 'application/pdf'),
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            }
        )
        
    except Exception as e:
        print(f"Error in save_pdf_annotation: {str(e)}")
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500





@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/comment/PdfAnnotation', methods=['POST'])
def post_annotation():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    annotation_data = request.get_json()
    print("Received annotation:", annotation_data)

    return jsonify({"status": "success"}), 200

# ... existing code ...

# @app.route('/api/annotations/load', methods=['POST'])
# def load_pdf_annotations():
#     try:
#         if 'file' not in request.files:
#             return jsonify({'error': 'No file provided'}), 400
            
#         pdf_file = request.files['file']
#         doc = None
        
#         try:
#             print("Starting to process PDF file...")
#             file_content = pdf_file.read()
#             doc = fitz.open(stream=file_content, filetype="pdf")
#             total_pages = len(doc)
            
#             annotations_by_page = {}
#             total_annotations = 0
            
#             # First pass: collect all annotations
#             for page_num in range(total_pages):
#                 page = doc[page_num]
#                 page_annotations = []
                
#                 # Get page dimensions
#                 page_rect = page.rect
#                 page_width = page_rect.width
#                 page_height = page_rect.height
                
#                 # Get all annotations and images on the page
#                 annots = list(page.annots())
#                 images = page.get_images()
                
#                 print(f"Page {page_num + 1}: Found {len(annots)} annotations and {len(images)} images")
                
#                 # Process regular annotations
#                 for annot in annots:
#                     try:
#                         annot_type = annot.type[1]
#                         rect = annot.rect
                        
#                         if not rect:
#                             continue
                            
#                         print(f"Processing annotation type: {annot_type}")
                        
#                         # Map polyline annotations to cloud or freeDraw based on properties
#                         if annot_type == 'PolyLine':
#                             vertices = annot.vertices if hasattr(annot, 'vertices') else []
#                             if vertices:
#                                 if len(vertices) > 4 and vertices[0] == vertices[-1]:
#                                     annot_type = 'Cloud'
#                                 else:
#                                     annot_type = 'FreeDraw'
                        
#                         # Get annotation content and subject
#                         content = annot.info.get('content', '')
#                         subject = annot.info.get('subject', '')
                        
#                         # Handle special cases for stamps and signatures
#                         if annot_type == 'Text' and any(word in subject.lower() for word in ['stamp', 'signature']):
#                             annot_type = 'Stamp' if 'stamp' in subject.lower() else 'Signature'
                        
#                         # Get annotation color
#                         color = None
#                         if hasattr(annot, 'colors') and annot.colors:
#                             color_values = annot.colors.get('stroke') or annot.colors.get('fill')
#                             if color_values:
#                                 color = f"rgb({int(color_values[0]*255)}, {int(color_values[1]*255)}, {int(color_values[2]*255)})"
                        
#                         annotation_data = {
#                             'id': str(uuid.uuid4()),
#                             'type': map_annotation_type(annot_type),
#                             'page': page_num + 1,
#                             'userName': annot.info.get('title', 'Unknown User'),
#                             'content': content,
#                             'subject': subject,
#                             'createdAt': datetime.now().isoformat(),
#                             'x1': rect.x0,
#                             'y1': rect.y0,
#                             'x2': rect.x1,
#                             'y2': rect.y1,
#                             'width': rect.x1 - rect.x0,
#                             'height': rect.y1 - rect.y0,
#                             'color': color,
#                             'isExisting': True,
#                             # Add page dimension information
#                             'pageWidth': page_width,
#                             'pageHeight': page_height,
#                             # Add scale information (default PDF points to pixels)
#                             'scale': 1.0
#                         }
                        
#                         page_annotations.append(annotation_data)
#                         total_annotations += 1
                        
#                     except Exception as e:
#                         print(f"Error processing annotation: {str(e)}")
#                         continue
                
#                 # Store annotations if any were found
#                 if page_annotations:
#                     annotations_by_page[str(page_num + 1)] = page_annotations
            
#             # Second pass: remove only cloud, stamp, and signature annotations
#             # ... (rest of the code remains the same) ...
            
#             response_data = {
#                 'annotations': annotations_by_page,
#                 'metadata': {
#                     'totalPages': total_pages,
#                     'totalAnnotations': total_annotations,
#                     'pagesInfo': {
#                         str(i+1): {
#                             'width': doc[i].rect.width,
#                             'height': doc[i].rect.height,
#                             'rotation': doc[i].rotation
#                         } for i in range(total_pages)
#                     }
#                 },
#                 'pdfContent': base64.b64encode(pdf_content).decode('utf-8')
#             }
            
#             print(f"Successfully processed {total_annotations} annotations")
#             return jsonify(response_data)
            
            
#         except Exception as e:
#             print(f"Error in processing: {str(e)}")
#             return jsonify({'error': f'Error processing annotations: {str(e)}'}), 500
#         finally:
#             if doc:
#                 try:
#                     doc.close()
#                 except Exception as e:
#                     print(f"Error closing document: {str(e)}")
                
#     except Exception as e:
#         print(f"General error: {str(e)}")
#         return jsonify({'error': str(e)}), 500

# # ... existing code ...

# def map_annotation_type(pymupdf_type):
#     type_mapping = {
#         'Square': 'square',
#         'Circle': 'circle',
#         'Line': 'line',
#         # 'FreeText': 'text',
#         'Text': 'text',
#         'Highlight': 'highlight',
#         'Underline': 'underline',
#         'StrikeOut': 'strikeout',
#         'FreeDraw': 'freeDraw',
#         'Stamp': 'stamp',
#         'Signiture' : 'signiture',
#         'Cloud' : 'cloud',
#     }
#     return type_mapping.get(pymupdf_type, 'unknown')



                             # For IIS 


# class PDFAnnotationProcessor:
#     def __init__(self, pdf_document):
#         self.doc = pdf_document
#         self.annotation_types = {
#             'Square': 'square',
#             'Circle': 'circle',
#             'Line': 'line',
#             'Text': 'text',
#             'Highlight': 'highlight',
#             'Underline': 'underline',
#             'StrikeOut': 'strikeout',
#             'PolyLine': 'freeDraw',
#             'Stamp': 'stamp',
#             'Ink': 'signature',
#             'Polygon': 'cloud'
#         }
#         print(f"Initialized PDFAnnotationProcessor with document length: {len(pdf_document)} pages")

#     def extract_annotations(self):
#         """Extract all annotations from the PDF document."""
#         annotations_by_page = {}
#         total_annotations = 0
        
#         print("\n=== Starting Annotation Extraction ===")
        
#         # Extract annotations
#         for page_num in range(len(self.doc)):
#             print(f"\nProcessing page {page_num + 1}")
#             page_annotations = []
#             page = self.doc[page_num]
#             annots = list(page.annots())
            
#             if annots:
#                 print(f"Found {len(annots)} annotations on page {page_num + 1}")
#                 for annot in annots:
#                     try:
#                         print(f"\nProcessing annotation: Type={annot.type[1]}")
#                         total_annotations += 1
#                         annotation_data = self._process_annotation(annot, page_num + 1)
#                         if annotation_data:
#                             page_annotations.append(annotation_data)
#                     except Exception as e:
#                         print(f"Error processing annotation: {str(e)}")
#                         continue
                
#             if page_annotations:
#                 annotations_by_page[str(page_num + 1)] = page_annotations
        
#         print(f"\nTotal annotations found: {total_annotations}")
#         return annotations_by_page, total_annotations

#     # Rest of the class remains the same...

#     def _process_annotation(self, annot, page_num):
#         try:
#             print(f"\n--- Processing Annotation Details ---")
#             annot_type = annot.type[1]
#             rect = annot.rect
            
#             print(f"Annotation Type: {annot_type}")
#             print(f"Rectangle: {rect}")
            
#             if not rect:
#                 print("No rectangle found for annotation")
#                 return None
                
#             # Map annotation type
#             mapped_type = self.annotation_types.get(annot_type, 'unknown')
#             print(f"Mapped type: {mapped_type}")
            
#             # Basic annotation data
#             annotation_data = {
#                 'id': str(uuid.uuid4()),
#                 'type': mapped_type,
#                 'page': page_num,
#                 'userName': annot.info.get('title', 'Unknown User'),
#                 'content': annot.info.get('content', ''),
#                 'subject': annot.info.get('subject', ''),
#                 'createdAt': datetime.now().isoformat(),
#                 'x1': rect.x0,
#                 'y1': rect.y0,
#                 'x2': rect.x1,
#                 'y2': rect.y1,
#                 'width': rect.width,
#                 'height': rect.height
#             }

#             # Process specific annotation types
#             if mapped_type in ['highlight', 'underline', 'strikeout']:
#                 print("Processing text-based annotation...")
#                 try:
#                     # Get the page object
#                     page = self.doc[page_num - 1]
                    
#                     # Extract text from the annotation's rectangle
#                     text = page.get_text("text", clip=rect)
#                     if text:
#                         annotation_data['text'] = text.strip()
#                         print(f"Extracted text: {annotation_data['text']}")
#                 except Exception as e:
#                     print(f"Error extracting text: {str(e)}")
#                     annotation_data['text'] = ''

#             elif mapped_type in ['stamp', 'signature']:
#                 print("Processing image-based annotation...")
#                 if hasattr(annot, 'get_pixmap'):
#                     try:
#                         pixmap = annot.get_pixmap()
#                         if pixmap:
#                             # Convert pixmap to PNG data
#                             img_data = pixmap.tobytes("png")
#                             annotation_data['imageData'] = base64.b64encode(img_data).decode('utf-8')
#                             print("Successfully extracted image data")
#                     except Exception as e:
#                         print(f"Error extracting image: {str(e)}")

#             elif mapped_type in ['freeDraw', 'cloud']:
#                 print("Processing path-based annotation...")
#                 if hasattr(annot, 'vertices'):
#                     vertices = annot.vertices
#                     if vertices:
#                         path = []
#                         for i, vertex in enumerate(vertices):
#                             if isinstance(vertex, (tuple, list)):
#                                 x, y = vertex
#                             else:
#                                 x, y = vertex.x, vertex.y
#                             path.append(['M' if i == 0 else 'L', x, y])
#                         annotation_data['path'] = path
#                         print(f"Extracted path with {len(path)} points")

#             # Get annotation color
#             if hasattr(annot, 'colors'):
#                 colors = annot.colors
#                 if colors:
#                     stroke_color = colors.get('stroke')
#                     if stroke_color:
#                         annotation_data['color'] = f"rgb({int(stroke_color[0]*255)}, {int(stroke_color[1]*255)}, {int(stroke_color[2]*255)})"
#                         print(f"Extracted color: {annotation_data['color']}")

#             print("Successfully processed annotation")
#             return annotation_data

#         except Exception as e:
#             print(f"Error processing annotation: {str(e)}")
#             print(f"Annotation object details: {vars(annot) if hasattr(annot, '__dict__') else 'No details available'}")
#             return None


# def remove_annotations_from_pdf(doc):
#     """Remove all annotations from a PDF while preserving the original document structure."""
#     print("\n=== Removing annotations from PDF ===")
#     total_removed = 0
    
#     # Create a new PDF document
#     new_doc = fitz.open()
    
#     try:
#         # Copy each page without annotations
#         for page_num in range(len(doc)):
#             # Insert page without annotations
#             new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num, annots=False)
#             print(f"Processed page {page_num + 1}")
            
#             # Count annotations that were on the original page
#             original_page = doc[page_num]
#             annot_count = len(list(original_page.annots()))
#             total_removed += annot_count
            
#             if annot_count > 0:
#                 print(f"Removed {annot_count} annotations from page {page_num + 1}")
#             else:
#                 print(f"No annotations found on page {page_num + 1}")
        
#         # Copy the cleaned content back to the original document
#         doc.delete_pages(range(len(doc)))  # Clear original document
#         doc.insert_pdf(new_doc)  # Insert cleaned pages
        
#         print(f"Total annotations removed: {total_removed}")
#         return total_removed
        
#     finally:
#         if new_doc:
#             new_doc.close()

# @app.route('/api/annotations/load', methods=['POST'])
# def load_pdf_annotations():
#     try:
#         print("\n=== Starting PDF Annotation Load ===")
        
#         if 'file' not in request.files:
#             return jsonify({'error': 'No file provided'}), 400
            
#         pdf_file = request.files['file']
#         doc = None
#         new_doc = None
        
#         try:
#             # Read file content into memory
#             file_content = pdf_file.read()
#             input_buffer = io.BytesIO(file_content)
            
#             # Open PDF from memory buffer
#             doc = fitz.open(stream=input_buffer, filetype="pdf")
            
#             # Process and extract annotations
#             processor = PDFAnnotationProcessor(doc)
#             annotations_by_page, total_annotations = processor.extract_annotations()
            
#             # Remove annotations and get clean PDF
#             total_removed = remove_annotations_from_pdf(doc)
            
#             # Save the modified PDF to memory
#             output_buffer = io.BytesIO()
#             doc.save(
#                 output_buffer,
#                 garbage=True,
#                 deflate=True,
#                 clean=True,
#                 linear=True
#             )
#             modified_pdf_content = output_buffer.getvalue()
            
#             # Create response
#             response_data = {
#                 'annotations': annotations_by_page,
#                 'metadata': {
#                     'totalPages': len(doc),
#                     'totalAnnotations': total_annotations,
#                     'removedAnnotations': total_removed,
#                     'pagesInfo': {
#                         str(i+1): {
#                             'width': doc[i].rect.width,
#                             'height': doc[i].rect.height,
#                             'rotation': doc[i].rotation
#                         } for i in range(len(doc))
#                     }
#                 },
#                 'pdfContent': base64.b64encode(modified_pdf_content).decode('utf-8')
#             }
            
#             return jsonify(response_data)
            
#         finally:
#             if doc:
#                 doc.close()
#             # Clean up memory buffers
#             if 'input_buffer' in locals():
#                 input_buffer.close()
#             if 'output_buffer' in locals():
#                 output_buffer.close()
                    
#     except Exception as e:
#         print(f"Error: {str(e)}")
#         print(f"Stack trace: {traceback.format_exc()}")
#         return jsonify({'error': str(e)}), 500


@app.route('/load-pdf/<path:encoded_url>')
def load_pdf_from_url(encoded_url):
    try:
        # Decode base64 URL
        try:
            decoded_url = base64.b64decode(encoded_url).decode('utf-8')
        except Exception as e:
            print(f"Error decoding URL: {str(e)}")
            return jsonify({"error": "Invalid URL encoding"}), 400

        print(f"Attempting to fetch PDF from: {decoded_url}")

        # Validate URL
        parsed_url = urlparse(decoded_url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            error_msg = "Invalid URL format"
            print(f"Error: {error_msg}")
            return jsonify({"error": error_msg}), 400

        if not decoded_url.lower().endswith('.pdf'):
            error_msg = "Invalid PDF URL"
            print(f"Error: {error_msg}")
            return jsonify({"error": error_msg}), 400
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/pdf,*/*',
            'Connection': 'keep-alive'
        }
        
        response = requests.get(
            decoded_url,
            headers=headers,
            verify=False,
            allow_redirects=True,
            timeout=30
        )

        print(f"Response status code: {response.status_code}")
        print(f"Response headers: {response.headers}")
        
        if response.status_code != 200:
            error_msg = f"Failed to fetch PDF: {response.status_code}"
            print(error_msg)
            return jsonify({"error": error_msg}), response.status_code

        content_type = response.headers.get('content-type', '')
        print(f"Content type: {content_type}")

        if len(response.content) == 0:
            print("Error: Empty PDF content")
            return jsonify({"error": "Empty PDF content"}), 400
        
        return send_file(
            io.BytesIO(response.content),
            mimetype='application/pdf',
            as_attachment=False,
            download_name='document.pdf'
        )
        
    except requests.RequestException as e:
        error_msg = f"Request error: {str(e)}"
        print(error_msg)
        return jsonify({"error": error_msg}), 500
    except Exception as e:
        error_msg = f"General error: {str(e)}"
        print(error_msg)
        return jsonify({"error": error_msg}), 500

@app.route('/view-pdf')
def view_pdf():
    return render_template('index.html')




                                # For Local Server App.py

# @app.route('/load-pdf/<path:pdf_url>')
# def load_pdf_from_url(pdf_url):
#     try:
#         decoded_url = unquote(pdf_url)
#         print(f"Attempting to fetch PDF from: {decoded_url}")  
        
#         if not decoded_url.lower().endswith('.pdf'):
#             return "Invalid PDF URL", 400
        
#         headers = {
#             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
#             'Accept': 'application/pdf,*/*'
#         }
        
#         response = requests.get(
#             decoded_url,
#             headers=headers,
#             verify=False,  
#             allow_redirects=True, 
#             # timeout=30  
#         )
        
#         if response.status_code != 200:
#             return f"Failed to fetch PDF: {response.status_code}", response.status_code

#         content_type = response.headers.get('content-type', '')
#         if 'application/pdf' not in content_type.lower() and 'application/octet-stream' not in content_type.lower():
#             print(f"Warning: Unexpected content type: {content_type}")  
        
#         return send_file(
#             io.BytesIO(response.content),
#             mimetype='application/pdf',
#             as_attachment=False,
#             download_name='document.pdf'
#         )
        
#     except requests.RequestException as e:
#         print(f"Request error: {str(e)}")  
#         return f"Error fetching PDF: {str(e)}", 500
#     except Exception as e:
#         print(f"General error: {str(e)}")  
#         return f"Server error: {str(e)}", 500

# @app.route('/view-pdf')
# def view_pdf():
#     return render_template('index.html')





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

# @app.route('/save', methods=['POST'])
# def save_pdf():
#     try:
#         data = request.get_json()

#         if not data or 'pdf' not in data or 'annotations' not in data:
#             return jsonify({"error": "Missing required data"}), 400
        

#         try:
#             pdf_data = base64.b64decode(data['pdf'])
#         except Exception as e:
#             return jsonify({"error": f"Invalid PDF data: {str(e)}"}), 400

        
#         annotations = data.get('annotations', [])
#         save_Path = data.get('savePath', 'D:/Publish Code/PdfAnnotation/Temp')

#         os.makedirs(save_Path, exist_ok=True)
#         timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
#         file_name = f'annotated_{timestamp}.pdf'
#         file_path = os.path.join(save_Path, file_name)

#         doc = fitz.open(stream=pdf_data, filetype="pdf")
        
#         for annotation in annotations:
#             try:
#                 page_num = annotation.get("page", 1) - 1
#                 page = pdf_document[page_num]

#                 if annotation["type"] == "text":
#                     if all(key in annotation for key in ["x1", "y1", "x2", "y2", "text"]):
#                         rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
#                         text_annotation = page.add_freetext_annot(rect, annotation["text"])
                        
#                         text_annotation.set_colors(stroke=(0, 0, 0), fill=(1, 1, 1))  # Black text, white background
#                         # text_annotation.update(fontsize=annotation.get("fontSize", 12),  # Set font size
#                                             # text_color=(0, 0, 0),  # Black text
#                                             # border_color=(0, 0, 0),  # Black border
#                                             # fill_color=(1, 1, 1))  # White background
                        
#                         text_annotation.set_info(
#                             title=annotation.get("title", "Text Annotation"),
#                             subject=annotation.get("subject", "Text"),
#                             content=annotation.get("content", annotation["text"])
#                         )
                        
#                         text_annotation.set_border(width=0.5)  # Add a slight border
#                         text_annotation.update()
                        
#                         # Draw the text directly on the page as a backup
#                         page.insert_text(
#                             point=fitz.Point(annotation["x1"], annotation["y1"] + 12),  # Adjust Y for baseline
#                             text=annotation["text"],
#                             # fontsize=annotation.get("fontSize", 12),
#                             # color=(0, 0, 0)  # Black color
#                         )
#                     else:
#                         print(f"Missing coordinates or text for text annotation: {annotation}")

#                 elif annotation["type"] == "line":
#                     if all(key in annotation for key in ["x1", "y1", "x2", "y2"]):
#                         start = fitz.Point(annotation["x1"], annotation["y1"])
#                         end = fitz.Point(annotation["x2"], annotation["y2"])

#                         # Create a line annotation instead of just drawing the line
#                         line_annot = page.add_line_annot(start, end)

#                         # Set additional metadata for the annotation
#                         line_annot.set_info(
#                             title=annotation.get("title", ""),
#                             subject=annotation.get("subject", ""),
#                             content=annotation.get("content", "")
#                         )

#                        # Set line properties
#                         line_annot.set_colors(stroke=(1, 0, 0))  # Red color
#                         line_annot.set_border(width=annotation.get("strokeWidth", 1))

#                         # Finalize the annotation
#                         line_annot.update()
#                     else:
#                         print(f"Missing coordinates for line annotation: {annotation}")

#                 elif annotation["type"] == "highlight":
#                     if "x1" in annotation and "y1" in annotation and "x2" in annotation and "y2" in annotation:
#                         rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
#                         highlight_annot = page.add_highlight_annot(rect)
#                         highlight_annot.set_opacity(0.5)
#                         highlight_annot.set_info(
#                             title=annotation.get("title", ""),
#                             subject=annotation.get("subject", "Highlight"),
#                             content=annotation.get("content", "This text is highlighted.")
#                         )
#                         highlight_annot.update()
#                     elif "relativeRect" in annotation and "text" in annotation:
#                         rect_data = annotation["relativeRect"]
#                         rect = fitz.Rect(
#                             rect_data["left"], rect_data["top"],
#                             rect_data["left"] + rect_data["width"],
#                             rect_data["top"] + rect_data["height"]
#                         )
#                         highlight_annot = page.add_highlight_annot(rect)
#                         highlight_annot.set_opacity(0.5)
#                         highlight_annot.set_info(
#                             title=annotation.get("title", ""),
#                             subject=annotation.get("subject", "Highlight"),
#                             content=annotation.get("content", "This text is highlighted.")
#                         )
#                         highlight_annot.update()
                        
#                     elif "lineAnnotations" in annotation:
#                         # List to hold individual bounding boxes for line annotations
#                         rects = []

#                         # Iterate through all line annotations and create bounding boxes for each one
#                         for line in annotation["lineAnnotations"]:
#                             if "left" in line and "top" in line and "width" in line and "height" in line:
#                                 # Create a bounding box for the current line annotation
#                                 rect = fitz.Rect(line["left"], line["top"], line["left"] + line["width"], line["top"] + line["height"])
#                                 rects.append(rect)  # Add the rect to the list
#                             else:
#                                 print(f"Missing coordinates for line annotation: {line}")

#                         # If we have valid bounding boxes, create highlight annotations
#                         if rects:
#                             for rect in rects:
#                                 if rect.width > 0 and rect.height > 0:
#                                     highlight_annot = page.add_highlight_annot(rect)
#                                     highlight_annot.set_opacity(0.5)
#                                     highlight_annot.set_info(
#                                         title=annotation.get("title", ""),
#                                         subject=annotation.get("subject", "Highlight"),
#                                         content=annotation.get("content", "This text is highlighted.")
#                                     )
#                                     highlight_annot.update()
#                             # print(f"Highlight annotation: Title: {annotation.get('title', '')}, Subject: {annotation.get('subject', 'Highlight')}, Content: {annotation.get('content', 'This text is highlighted.')}, Coordinates: {annotation['x1']}, {annotation['y1']} to {annotation['x2']}, {annotation['y2']}")
#                         else:
#                             print("No valid line annotations found.")


                
#                     else:
#                         print(f"Missing coordinates for highlight annotation: {annotation} (Check if 'relativeRect' or 'text' is missing)")


#                 elif annotation["type"] == "underline":
#                     if "x1" in annotation and "y1" in annotation and "x2" in annotation and "y2" in annotation:
#                         # Case with explicit coordinates
#                         rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
#                         underline_annot = page.add_underline_annot(rect)
#                         underline_annot.set_colors(stroke=(1, 0, 0))  # Optional: red color for underline
#                         underline_annot.set_info(
#                             title=annotation.get("title", ""),
#                             subject=annotation.get("subject", "Underline"),
#                             content=annotation.get("content", "This text is underlined.")
#                         )
#                         underline_annot.update()
#                     elif "relativeRect" in annotation and "text" in annotation:
#                         # Case with relativeRect
#                         rect_data = annotation["relativeRect"]
#                         rect = fitz.Rect(
#                             rect_data["left"], rect_data["top"],
#                             rect_data["left"] + rect_data["width"],
#                             rect_data["top"] + rect_data["height"]
#                         )
#                         underline_annot = page.add_underline_annot(rect)
#                         underline_annot.set_colors(stroke=(1, 0, 0))  # Set color to red
#                         # underline_annot.set_text(annotation["text"])
#                         underline_annot.set_info(
#                             title=annotation.get("title", ""),
#                             subject=annotation.get("subject", "Underline"),
#                             content=annotation.get("content", "This text is underlined.")
#                         )
#                         underline_annot.update()
#                     elif annotation["type"] == "underline":
#                         if "lineAnnotations" in annotation:
#                             for line in annotation["lineAnnotations"]:
#                                 if "left" in line and "top" in line and "width" in line and "height" in line:
#                                     rect = fitz.Rect(
#                                         line["left"],
#                                         line["top"],
#                                         line["left"] + line["width"],
#                                         line["top"] + line["height"]
#                                     )
#                                     if rect.width > 0 and rect.height > 0:
#                                         underline_annot = page.add_underline_annot(rect)
#                                         underline_annot.set_colors(stroke=(1, 0, 0))  # Optional: red color for underline
#                                         underline_annot.set_info(
#                                             title=annotation.get("title", ""),
#                                             subject=annotation.get("subject", "Underline"),
#                                             content=annotation.get("content", "This text is underlined.")
#                                         )
#                                         underline_annot.update()
                    
#                                 else:
#                                     print(f"Missing coordinates for line annotation: {line}")                      
#                         else:
#                             print(f"Missing line annotations for underline annotation: {annotation}")

#                 elif annotation["type"] == "strikeout":
#                     if all(key in annotation for key in ["x1", "y1", "x2", "y2"]):
#                         rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
#                         strikeout_annot = page.add_strikeout_annot(rect)
#                         strikeout_annot.set_colors(stroke=(1, 0, 0))
#                         strikeout_annot.set_border(width=annotation.get("strokeWidth", 1))
#                         strikeout_annot.set_info(
#                             title=annotation.get("title", "Strike-out"),
#                             subject=annotation.get("subject", "Strike-out Annotation"),
#                             content=annotation.get("content", "This text has been struck out.")
#                         )
#                         strikeout_annot.update()
#                     elif "relativeRect" in annotation and "text" in annotation:
#                         rect_data = annotation["relativeRect"]
#                         rect = fitz.Rect(
#                             rect_data["left"], rect_data["top"],
#                             rect_data["left"] + rect_data["width"],
#                             rect_data["top"] + rect_data["height"]
#                         )
#                         # y_mid = rect.top + (rect.height / 2)
#                         strikeout_annot = page.add_strikeout_annot(rect)
#                         strikeout_annot.set_colors(stroke=(1, 0, 0))  # Red color for strikeout
#                         strikeout_annot.set_border(width=annotation.get("strokeWidth", 1))
#                         strikeout_annot.set_info(
#                             title=annotation.get("title", "Strike-out"),
#                             subject=annotation.get("subject", "Strike-out Annotation"),
#                             content=annotation.get("content", "This text has been struck out.")
#                         )
#                         strikeout_annot.update()
#                     elif annotation["type"] == "strikeout":
#                         if "lineAnnotations" in annotation:
#                             for line in annotation["lineAnnotations"]:
#                                 if "left" in line and "top" in line and "width" in line and "height" in line:
#                                     rect = fitz.Rect(
#                                         line["left"],
#                                         (line["top"])-8,
#                                         line["left"] + line["width"],
#                                         line["top"] + line["height"]
#                                     )
#                                     if rect.width > 0 and rect.height > 0:
#                                         strikeout_annot = page.add_strikeout_annot(rect)
#                                         strikeout_annot.set_colors(stroke=(1, 0, 0))  # Optional: red color for strikeout
#                                         # strikeout_annot.set_border(dashes=0, width=1)  # Set stroke width
#                                         strikeout_annot.set_border(width=annotation.get("strokeWidth", 1))

#                                         strikeout_annot.set_info(
#                                             title=annotation.get("title", ""),
#                                             subject=annotation.get("subject", "Strikeout"),
#                                             content=annotation.get("content", "This text is struck out.")
#                                         )
#                                         strikeout_annot.update()
#                                         print(annotation)
#                                 else:
#                                     print(f"Missing coordinates for line annotation: {line}")
#                     else:
#                         print(f"Missing coordinates for strike-out annotation: {annotation}")
                    
#                 elif annotation["type"] == "stamp":
#                     img_src = annotation.get("imgSrc")
#                     x1 = annotation.get("x1")
#                     y1 = annotation.get("y1")
#                     x2 = annotation.get("x2")
#                     y2 = annotation.get("y2")

#                     if img_src and x1 is not None and y1 is not None and x2 is not None and y2 is not None:
#                         width = x2 - x1
#                         height = y2 - y1

#                         img_path = os.path.join(os.getcwd(), img_src.lstrip('/'))  # Get the absolute path
#                         if os.path.exists(img_path):
#                             # Read the image as a byte stream
#                             with open(img_path, "rb") as img_file:
#                                 img_data = img_file.read()
                            
#                             # Use fitz to open the image as a stream
#                             img_rect = fitz.Rect(x1-300, y1-70, x2-50, y2-70)  # Define the rectangle area for the stamp
#                             page.insert_image(img_rect, stream=img_data, width=width, height=height)

#                         # Optionally, add metadata for the stamp annotation
#                         stamp_annot = page.add_text_annot(fitz.Rect(x1, y1, x2, y2), '')
#                         stamp_annot.set_info(
#                             title=annotation.get("title", "Stamp Annotation"),
#                             subject=annotation.get("subject", "Stamp Subject"),
#                             content=annotation.get("content", "This is a stamp annotation")
#                         )
#                         stamp_annot.update()

#                 elif annotation["type"] == "signature":
#                     img_data = annotation.get("dataURL")  # Base64-encoded image data
#                     x1, y1 = annotation.get("x1"), annotation.get("y1")
#                     x2, y2 = annotation.get("x2"), annotation.get("y2")

#                     # Validate essential fields
#                     if not img_data:
#                         print(f"Missing image data for signature annotation: {annotation}")
#                         continue
#                     if any(coord is None for coord in [x1, y1, x2, y2]):
#                         print(f"Invalid coordinates for signature annotation: {annotation}")
#                         continue

#                     try:
#                         # Decode base64 image data
#                         if "," in img_data:
#                             img_bytes = base64.b64decode(img_data.split(",")[1])
#                         else:
#                             img_bytes = base64.b64decode(img_data)

#                         # Validate image dimensions
#                         width = x2 - x1
#                         height = y2 - y1
#                         if width <= 0 or height <= 0:
#                             print(f"Invalid dimensions for signature annotation: {annotation}")
#                             continue

#                         # Create a rectangle for the image
#                         img_rect = fitz.Rect(x1-400, y1-80, x2, y2-80)

#                         # Insert the image into the PDF
#                         page.insert_image(img_rect, stream=io.BytesIO(img_bytes))
#                         sig_annot = page.add_text_annot(fitz.Rect(x1, y1, x2, y2), '')
#                         sig_annot.set_info(
#                             title=annotation.get("title", "Signature Annotation"),
#                             subject=annotation.get("subject", "Signature Subject"),
#                             content=annotation.get("content", "This is a signature annotation")
#                         )
#                         sig_annot.update()
#                         print(f"Signature annotation successfully added at page {annotation.get('page')}, coordinates: ({x1}, {y1}), ({x2}, {y2})")

#                     except Exception as e:
#                         print(f"Error adding signature annotation: {e}, annotation: {annotation}")


#                 elif annotation["type"] == "square":
#                     if all(key in annotation for key in ["x1", "y1", "x2", "y2"]):
#                         rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
#                         square_annot = page.add_rect_annot(rect)
#                         square_annot.set_info(
#                             title=annotation.get("title", ""),
#                             subject=annotation.get("subject", ""),
#                             content=annotation.get("content", "")
#                         )
#                         square_annot.set_colors(stroke=[1, 0, 0])  # Red in RGB format
#                         square_annot.set_border(width=annotation.get("strokeWidth", 1))
#                         square_annot.update()
#                         # print(f"Added square annotation: {annotation}")
#                     else:
#                         print(f"Missing coordinates for square annotation: {annotation}")

#                 elif annotation["type"] == "circle":
#                     if all(key in annotation for key in ["x1", "y1", "radius"]):
#                         radius = annotation["radius"]
#                         if radius > 0:
#                             rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x1"] + radius * 2, annotation["y1"] + radius * 2)
#                             circle_annot = page.add_circle_annot(rect)
#                             circle_annot.set_info(
#                                 title=annotation.get("title", ""),
#                                 subject=annotation.get("subject", ""),
#                                 content=annotation.get("content", "")
#                             )
#                             circle_annot.set_border(width=2)  # Set stroke width to 2

#                             circle_annot.update()
#                         else:
#                             print(f"Invalid radius for circle annotation: {annotation}")
#                     else:
#                         print(f"Missing data for circle annotation: {annotation}")

#                 elif annotation["type"] == "cloud":
#                     if "path" in annotation and isinstance(annotation["path"], list):
#                         cloud_path = annotation['path']
#                         points = []
#                         for command in cloud_path:
#                             if command[0] == 'M':
#                                 points.append(fitz.Point(command[1], command[2]))
#                             elif command[0] == 'L':
#                                 points.append(fitz.Point(command[1], command[2]))
#                             elif command[0] == 'C':
#                                 points.append(fitz.Point(command[1], command[2]))
#                                 points.append(fitz.Point(command[3], command[4]))
#                                 points.append(fitz.Point(command[5], command[6]))
#                         try:
#                             cloud_annot = page.add_polyline_annot(points)
#                             cloud_annot.set_info(
#                                 title=annotation.get("title", "Cloud Annotation"),
#                                 subject=annotation.get("subject", "Cloud"),
#                                 content=annotation.get("content", "")
#                            )
#                             page.draw_polyline(
#                                 points,
#                                 color=(1, 0, 0),
#                                 width=annotation.get("strokeWidth", 2),
#                                 closePath=True
#                             )
#                         except Exception as e:
#                             print(f"Error drawing cloud annotation: {e}")
#                     else:
#                         print(f"Missing path data for cloud annotation: {annotation}")

#                 elif annotation["type"] == "freeDraw":
#                     if "path" in annotation:
#                         path = annotation["path"]
#                         fitz_path = []

#                         for command in path:
#                             if command[0] == 'M':  # Move to
#                                 fitz_path.append(fitz.Point(command[1], command[2]))
#                             elif command[0] == 'Q':  # Quadratic curve
#                                 fitz_path.append(fitz.Point(command[1], command[2]))
#                                 fitz_path.append(fitz.Point(command[3], command[4]))

#                         # Create a polyline annotation for FreeDraw
#                         free_draw_annot = page.add_polyline_annot(fitz_path)

#                         # Set metadata for the annotation
#                         free_draw_annot.set_info(
#                            title=annotation.get("title", ""),
#                             subject=annotation.get("subject", ""),
#                             content=annotation.get("content", "")
#                         )

#                         # Set appearance properties
#                         free_draw_annot.set_colors(stroke=(1, 0, 0))  # Red color
#                         free_draw_annot.set_border(width=annotation.get("strokeWidth", 2))

#                         # Finalize the annotation
#                         free_draw_annot.update()
#                     else:
#                         print(f"Missing path data for freeDraw annotation: {annotation}")

              
#             except Exception as e:
#                 print(f"Error processing annotation {annotation}: {e}")

#         output_stream = io.BytesIO()
#         doc.save(file_path)
#         annotated_pdf = output_stream.getvalue()
#         doc.close()

#         # return jsonify({
#         #     "message": "PDF saved successfully",
#         #     "filePath": file_path
#         # }), 200

#         try:
#             conn = get_db_connection()
#             cursor = conn.cursor()

#             cursor.execute("""
#                 INSERT INTO PDFDocuments (FileName, FilePath)
#                 OUTPUT INSERTED.Id
#                 VALUES (?, ?)
#             """, (file_name, file_path))
            
#             row = cursor.fetchone()
#             if row:
#                 pdf_id = row[0]

#             for annotation in annotations:
#                 cursor.execute("""
#                     INSERT INTO Annotations 
#                     (PDFDocumentId, Type, PageNumber, X1, Y1, X2, Y2, Content)
#                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)
#                 """, (
#                     pdf_id,
#                     annotation.get('type', ''),
#                     annotation.get('page', 1),
#                     annotation.get('x1', 0),
#                     annotation.get('y1', 0),
#                     annotation.get('x2', 0),
#                     annotation.get('y2', 0),
#                         annotation.get('content', '')
#                     ))
                

        
#             conn.commit()


#             for annotation in annotations:
#                 cursor.execute("""
#                     INSERT INTO Annotations (PDFDocumentId, AnnotationType, PageNumber, AnnotationData, CreatedDate, ModifiedDate)
#                     VALUES (?, ?, ?, ?, GETDATE(), GETDATE())
#                 """, (
#                     pdf_id,
#                     annotation['type'],
#                     annotation.get('page', 1),
#                     json.dumps(annotation)
#                 ))

#             conn.commit()
#             conn.close()
        
#         except pyodbc.Error as e:
#             print(f"Database error: {str(e)}")
#             if 'conn' in locals():
#                 conn.rollback()
#             raise
#         finally:
#             if 'conn' in locals():
#                 conn.close()

#         output_stream.seek(0)
#         with open(file_path, 'rb') as f:
#             pdf_content = f.read()

#         try:
#             os.remove(file_path)
#         except:
#             pass

#         response = send_file(
#             io.BytesIO(pdf_content),
#             mimetype='application/pdf',
#             as_attachment=True,
#             download_name=file_name
#         )

#         response.headers['X-Save-Path'] = file_path
#         return response

        

#     except Exception as e:
#         print(f"Error in save_pdf: {e}")
#         return jsonify({"error": str(e)}), 500


# @app.route('/documents', methods=['GET'])
# def get_documents():
#     try:
#         conn = get_db_connection()
#         cursor = conn.cursor()
        
#         cursor.execute("SELECT DocumentID, FileName, UploadDate FROM PDFDocuments ORDER BY UploadDate DESC")
#         documents = [{"id": row[0], "filename": row[1], "upload_date": row[2]} for row in cursor.fetchall()]
        
#         conn.close()
#         return jsonify(documents)
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# @app.route('/test-db')
# def test_db():
#     try:
#         conn = get_db_connection()
#         cursor = conn.cursor()
        
#         # Test PDFDocuments table
#         cursor.execute("SELECT TOP 1 * FROM PDFDocuments")
#         pdf_cols = [column[0] for column in cursor.description]
        
#         # Test Annotations table
#         cursor.execute("SELECT TOP 1 * FROM Annotations")
#         ann_cols = [column[0] for column in cursor.description]
        
#         conn.close()
        
#         return jsonify({
#             "status": "success",
#             "PDFDocuments_columns": pdf_cols,
#             "Annotations_columns": ann_cols
#         })
#     except Exception as e:
#         return jsonify({
#             "status": "error",
#             "message": str(e)
#         }), 500

# @app.route('/document/<int:document_id>', methods=['GET'])
# def get_document(document_id):
#     try:
#         conn = get_db_connection()
#         cursor = conn.cursor()
        
#         cursor.execute("SELECT AnnotatedPDF FROM PDFDocuments WHERE DocumentID = ?", (document_id,))
#         result = cursor.fetchone()
        
#         if result:
#             pdf_data = result[0]
#             return send_file(
#                 io.BytesIO(pdf_data),
#                 mimetype='application/pdf',
#                 as_attachment=True,
#                 download_name=f"document_{document_id}.pdf"
#             )
#         else:
#             return jsonify({"error": "Document not found"}), 404
            
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# @app.route('/annotations/<int:document_id>', methods=['GET'])
# def get_annotations(document_id):
#     try:
#         conn = get_db_connection()
#         cursor = conn.cursor()
        
#         cursor.execute("""
#             SELECT AnnotationType, PageNumber, AnnotationData 
#             FROM Annotations 
#             WHERE DocumentID = ? 
#             ORDER BY PageNumber, CreatedDate
#         """, (document_id,))
        
#         annotations = [
#             {
#                 "type": row[0],
#                 "page": row[1],
#                 "data": json.loads(row[2])
#             }
#             for row in cursor.fetchall()
#         ]
        
#         conn.close()
#         return jsonify(annotations)
#     except Exception as e:
        # return jsonify({"error": str(e)}), 500


# if __name__ == '__main__':
#     # app.run(debug=True, port=5000)  
#     app.run()

application = app

if __name__ == '__main__':
    try:
        logger.info('Starting Flask development server on port 80')
        app.run(host='0.0.0.0', port=80, debug=True)
    except Exception as e:
        logger.error(f'Failed to start Flask: {str(e)}')

# application = app

# if __name__ == '__main__':
#     app.run()
