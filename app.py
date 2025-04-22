import base64
import io
import uuid
import zipfile

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
import re
import pypdfium2
import math
from spire.pdf.common import *
from spire.pdf import *
# from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pdfrw import PdfReader, PdfWriter, PageMerge




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
        try:
            conn = None
            # conn =get_db_connection
            conn = get_db_connection()
            if not conn:
                    raise Exception("Failed to establish database connection")
                    
            cursor = conn.cursor()

            print("Received download request")
            
            if 'file' not in request.files:
                print("No file in request")
                return jsonify({"error": "No file part"}), 400
                
            file = request.files['file']
            annotations_json = request.form.get('annotations')
            document_id = request.form.get('DocumentId')
            user_id = None
            possible_user_id_fields = [
                request.form.get('userId'),
                request.form.get('UserId'),
                request.form.get('user_id'),
                request.headers.get('userId')
            ]

            if annotations_json:
                try:
                    annotations = json.loads(annotations_json)
                    if annotations and isinstance(annotations, list) and len(annotations) > 0:
                        user_id = annotations[0].get('userId') or annotations[0].get('UserId')
                except:
                    pass

            # Use the first non-None value found
            user_id = next((uid for uid in possible_user_id_fields if uid is not None), user_id)

            print(f"Received DocumentId: {document_id}")
            print(f"Received userId: {user_id}")
            print(f"Form Data: {request.form}")

            if not document_id:
                print("Missing DocumentId in request")
                return jsonify({"error": "Missing DocumentId"}), 400

            if not user_id:
                print("Missing userId in request")
                return jsonify({"error": "Missing userId"}), 400

            # Read the PDF file
            pdf_bytes = file.read()
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            annotations = json.loads(annotations_json)
            print(f"Processing {len(annotations)} annotations")

            # Process annotations (reuse your existing annotation processing code)
            for annotation in annotations:
                try:
                    page_num = int(annotation.get("page", 1))
                    if page_num <= 0:
                        page_num = 1
                    page = pdf_document[page_num - 1]  # Convert to 0-based index

                    if "documentId" not in annotation:
                        annotation["documentId"] = document_id
                    if "userId" not in annotation:
                        annotation["userId"] = user_id

                    
                    
                    print(f"Processing annotation type: {annotation['type']} on page {page_num}")

                    id_metadata = f"userId:{annotation['userId']};documentId:{annotation['documentId']};"

                    if "type" in annotation and annotation["type"] == "text" or all(key in annotation for key in ["x1", "y1", "x2", "y2", "text"]):
                        try:
                            print(f"Processing text annotation: {annotation}")
                            
                            # Create the rectangle for the text annotation
                            rect = fitz.Rect(
                                annotation["x1"], 
                                annotation["y1"], 
                                annotation["x2"], 
                                annotation["y2"]
                            )

                            annotation_text = annotation.get("content") 
                            
                            # Add the text annotation with proper parameters
                            text_annotation = page.add_freetext_annot(
                                rect=rect,
                                text=annotation_text,
                                fontsize=float(annotation.get("fontSize", 11)),
                                fontname="Helv",
                                text_color=(0, 0, 0),  # Black text
                                # fill_color=(1, 1, 1),  # White background
                                border_color=(0, 0, 0)  # Black border
                            )
                            
                            # Set metadata
                            text_annotation.set_info(
                                title=id_metadata,
                                subject=annotation.get("subject", "Text"),
                                content= annotation.get("content", annotation["text"])
                            )
                            
                            # Set border and make printable
                            text_annotation.set_border(width=0.5)
                            text_annotation.set_flags(fitz.PDF_ANNOT_IS_PRINT)
                            
                            # Update appearance
                            text_annotation.update()
                            # page.set_dirty()
                            
                            print("✅ Text annotation added successfully")
                            
                        except Exception as e:
                            print(f"Error processing text annotation: {e}")
                            traceback.print_exc()
                    
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
                                content=id_metadata + annotation.get("content", "")
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
                                content=id_metadata + annotation.get("content", "This text is highlighted.")
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
                                content=id_metadata + annotation.get("content", "This text is highlighted.")
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
                                            content=id_metadata + annotation.get("content", "This text is highlighted.")
                                        )
                                        highlight_annot.update()
                                        print(annotation)
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
                                content=id_metadata + annotation.get("content", "This text is underlined.")
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
                                content=id_metadata + annotation.get("content", "This text is underlined.")
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
                                                content=id_metadata + annotation.get("content", "This text is underlined.")
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
                                content=id_metadata + annotation.get("content", "This text has been struck out.")
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
                                content=id_metadata + annotation.get("content", "This text has been struck out.")
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
                                                content=id_metadata + annotation.get("content", "This text is struck out.")
                                            )
                                            strikeout_annot.update()
                                            print(annotation)
                                    else:
                                        print(f"Missing coordinates for line annotation: {line}")
                        else:
                            print(f"Missing coordinates for strike-out annotation: {annotation}")
                        
                    # elif annotation["type"] == "stamp":
                    #     img_src = annotation.get("imgSrc")
                    #     x1 = annotation.get("x1")
                    #     y1 = annotation.get("y1")
                    #     x2 = annotation.get("x2")
                    #     y2 = annotation.get("y2")

                    #     if img_src and x1 is not None and y1 is not None and x2 is not None and y2 is not None:
                    #         width = x2 - x1
                    #         height = y2 - y1

                    #         img_path = os.path.join(os.getcwd(), img_src.lstrip('/'))
                    #         if os.path.exists(img_path):
                    #             try:
                    #                 # Create the stamp rectangle with exact coordinates
                    #                 stamp_rect = fitz.Rect(x1, y1, x2, y2)
                                    
                    #                 # Create a stamp annotation
                    #                 stamp_annot = page.add_stamp_annot(stamp_rect)
                                    
                    #                 # Read and process the image
                    #                 with open(img_path, "rb") as img_file:
                    #                     img_data = img_file.read()
                                    
                    #                 # Set the appearance stream directly with the image data
                    #                 stamp_annot.set_appearance(stream=img_data, content=img_data)
                                    
                    #                 # Set PDF dictionary properties
                    #                 pdf_dict = stamp_annot.get_pdf_obj()
                    #                 pdf_dict.update({
                    #                     'Subtype': '/Stamp',
                    #                     'Name': '/StampAnnotation',
                    #                     'F': 4,  # Annotation flags
                    #                     'Rect': [stamp_rect.x0, stamp_rect.y0, stamp_rect.x1, stamp_rect.y1]
                    #                 })
                                    
                    #                 # Set metadata
                    #                 stamp_annot.set_info(
                    #                     title=annotation.get("userName", "Anurag Sable"),
                    #                     subject="Stamp",
                    #                     content=annotation.get("content", "This is a stamp annotation")
                    #                 )
                                    
                    #                 # Update the annotation
                    #                 stamp_annot.update()
                                    
                    #                 print(f"Stamp annotation added successfully at: {stamp_rect}")
                                    
                    #             except Exception as e:
                    #                 print(f"Error processing stamp annotation: {e}")
                    #                 print(f"Error details: {str(e)}")
                    #         else:
                    #             print(f"Image file not found: {img_path}")
                    #     else:
                    #         print("Missing required stamp annotation properties")

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
                                content=id_metadata + annotation.get("content", "This is a stamp annotation")
                            )
                            stamp_annot.update()

                    # elif annotation["type"] == "signature":
                    #     img_data = annotation.get("dataURL")
                    #     x1, y1 = annotation.get("x1"), annotation.get("y1")
                    #     x2, y2 = annotation.get("x2"), annotation.get("y2")

                    #     if img_data and None not in (x1, y1, x2, y2):
                    #         try:
                    #             # Decode base64 image data
                    #             if "," in img_data:
                    #                 img_bytes = base64.b64decode(img_data.split(",")[1])
                    #             else:
                    #                 img_bytes = base64.b64decode(img_data)

                    #             # Create a signature annotation
                    #             sig_rect = fitz.Rect(x1-400, y1-80, x2, y2-80)
                    #             sig_annot = page.add_stamp_annot(sig_rect)  # Use stamp annotation for signatures
                                
                    #             # Set the signature image as the appearance
                    #             sig_annot.set_appearance(stream=img_bytes, content=img_bytes)
                                
                    #             # Set metadata
                    #             sig_annot.set_info(
                    #                 title=annotation.get("userName", "Anurag Sable"),
                    #                 subject="Signature",
                    #                 content=annotation.get("content", "This is a signature annotation")
                    #             )
                    #             sig_annot.update()
                    #             print(f"Signature annotation successfully added at page {annotation.get('page')}")

                    #         except Exception as e:
                    #             print(f"Error adding signature annotation: {e}")

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
                                content=id_metadata + annotation.get("content", "This is a signature annotation")
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
                                content=id_metadata + annotation.get("content", "")
                            )
                            square_annot.set_colors(stroke=[1, 0, 0])  # Red in RGB format
                            square_annot.set_border(width=annotation.get("strokeWidth", 1))
                            square_annot.update()
                            print(f"Added square annotation: {annotation}")
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
                                    content=id_metadata + annotation.get("content", "")
                                )
                                circle_annot.set_border(width=2)  # Set stroke width to 2

                                circle_annot.update()
                            else:
                                print(f"Invalid radius for circle annotation: {annotation}")
                        else:
                            print(f"Missing data for circle annotation: {annotation}")

                    elif annotation["type"] == "cloud":
                        try:
                            print("Processing cloud annotation... Block 1")
                            if "path" in annotation and isinstance(annotation["path"], list):
                                try:
                                    print("Processing cloud annotation... Block 1.1")
                                    cloud_path = annotation['path']
                                    points = []
                                    vertices = []
                                    
                                    # Convert path commands to points with better curve handling
                                    current_point = None
                                    for command in cloud_path:
                                        try:
                                            if command[0] == 'M':  # Move to
                                                current_point = fitz.Point(command[1], command[2])
                                                points.append(current_point)
                                                vertices.append(current_point)
                                            elif command[0] == 'L':  # Line to
                                                current_point = fitz.Point(command[1], command[2])
                                                points.append(current_point)
                                                vertices.append(current_point)
                                            elif command[0] == 'C':  # Cubic bezier curve
                                                start = current_point
                                                c1 = fitz.Point(command[1], command[2])
                                                c2 = fitz.Point(command[3], command[4])
                                                end = fitz.Point(command[5], command[6])
                                                
                                                steps = 10
                                                for i in range(1, steps + 1):
                                                    t = i / steps
                                                    x = (1-t)**3 * start.x + 3*(1-t)**2 * t * c1.x + 3*(1-t) * t**2 * c2.x + t**3 * end.x
                                                    y = (1-t)**3 * start.y + 3*(1-t)**2 * t * c1.y + 3*(1-t) * t**2 * c2.y + t**3 * end.y
                                                    point = fitz.Point(x, y)
                                                    points.append(point)
                                                    vertices.append(point)
                                                current_point = end
                                        except Exception as e:
                                            print(f"Error processing command: {e}")
                                            continue

                                    print(f"Total points generated: {len(points)}")
                                    if points:
                                        try:
                                            cloud_annot = page.add_polyline_annot(points)
                                            cloud_annot.set_border(width=annotation.get("strokeWidth", 2))
                                            cloud_annot.set_colors(stroke=(1, 0, 0))  # Red color
                                            cloud_annot.set_info(
                                                title=annotation.get("userName", "Anurag Sable"),
                                                subject="Cloud",
                                                content=id_metadata + annotation.get("content", "")
                                            )

                                            if points[0] != points[-1]:
                                                points.append(points[0])
                                                vertices.append(vertices[0])

                                            cloud_annot.update()
                                            print(annotation)
                                            print(f"Cloud annotation added successfully")
                                        except Exception as e:
                                            print(f"Error creating cloud annotation: {e}")
                                    else:
                                        print("No valid points generated for cloud annotation")
                                except Exception as e:
                                    print(f"Error processing cloud path: {e}")
                                    raise  # Re-raise to trigger fallback
                            else:
                                raise ValueError("Invalid path format")  # Trigger fallback method

                        except Exception as e:
                            print(f"Error in first block cloud 1: {e}. Trying fallback method.")

                            try:
                                print("Using fallback method... Block 2")
                                if "path" in annotation:
                                    try:
                                        path = annotation["path"].split(' ')
                                        points = []
                                        vertices = []

                                        # Parse the path string into points
                                        for i in range(0, len(path), 3):
                                            try:
                                                command = path[i]
                                                if command == 'M' or command == 'L':
                                                    x = float(path[i + 1])
                                                    y = float(path[i + 2])
                                                    point = fitz.Point(x, y)
                                                    points.append(point)
                                                    vertices.append(point)
                                            except Exception as e:
                                                print(f"Error processing fallback command: {e}")
                                                continue

                                        print(f"Fallback: Total points generated: {len(points)}")
                                        if points:
                                            try:
                                                cloud_annot = page.add_polyline_annot(points)
                                                cloud_annot.set_border(width=annotation.get("strokeWidth", 2))
                                                cloud_annot.set_colors(stroke=(1, 0, 0))  # Red color
                                                cloud_annot.set_info(
                                                    title=annotation.get("userName", "Anurag Sable"),
                                                    subject="Cloud",
                                                    content=id_metadata + annotation.get("content", "")
                                                )

                                                if points[0] != points[-1]:
                                                    points.append(points[0])
                                                    vertices.append(vertices[0])

                                                cloud_annot.update()
                                                print(f"Cloud annotation added successfully (fallback method)")
                                            except Exception as e:
                                                print(f"Error creating cloud annotation in fallback: {e}")
                                        else:
                                            print("No valid points generated in fallback method")
                                    except Exception as e:
                                        print(f"Error processing fallback path: {e}")
                                else:
                                    print("No path data available for fallback method")
                            except Exception as e:
                                print(f"Error in fallback block cloud: {e}")
                    # elif annotation["type"] == "cloud":
                    #     if "path" in annotation and isinstance(annotation["path"], list):
                    #         cloud_path = annotation['path']
                    #         points = []
                    #         for command in cloud_path:
                    #             if command[0] == 'M':
                    #                 points.append(fitz.Point(command[1], command[2]))
                    #             elif command[0] == 'L':
                    #                 points.append(fitz.Point(command[1], command[2]))
                    #             elif command[0] == 'C':
                    #                 points.append(fitz.Point(command[1], command[2]))
                    #                 points.append(fitz.Point(command[3], command[4]))
                    #                 points.append(fitz.Point(command[5], command[6]))
                    #         try:
                    #             cloud_annot = page.add_polyline_annot(points)
                    #             cloud_annot.set_info(
                    #                 title=annotation.get("userName", "Anurag Sable"),
                    #                 subject=annotation.get("subject", "Cloud"),
                    #                 content=annotation.get("content", "")
                    #            )
                    #             page.draw_polyline(
                    #                 points,
                    #                 color=(1, 0, 0),
                    #                 width=annotation.get("strokeWidth", 2),
                    #                 closePath=True
                    #             )
                    #         except Exception as e:
                    #             print(f"Error drawing cloud annotation: {e}")
                    #     else:
                    #         print(f"Missing path data for cloud annotation: {annotation}")

                    elif annotation["type"] == "freeDraw":
                        try:
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
                                    content=id_metadata + annotation.get("content", "")
                                )

                                # Set appearance properties
                                free_draw_annot.set_colors(stroke=(1, 0, 0))  # Red color
                                free_draw_annot.set_border(width=annotation.get("strokeWidth", 2))

                                # Finalize the annotation
                                free_draw_annot.update()
                        except Exception as e:
                            print(f"Error in first block: {e}. Trying fallback method.")
                            
                            try:
                                if "path" in annotation:
                                    path = annotation["path"]
                                    fitz_path = []

                                    # Convert path string to a list of commands
                                    if isinstance(path, str):
                                        path = path.split(' ')

                                    # Ensure path is a list of commands
                                    for i in range(0, len(path), 3):
                                        try:
                                            command = path[i:i+3]
                                            if command[0] == 'M' and len(command) >= 3:  # Move to
                                                fitz_path.append(fitz.Point(float(command[1]), float(command[2])))
                                            elif command[0] == 'L' and len(command) >= 3:  # Line to
                                                fitz_path.append(fitz.Point(float(command[1]), float(command[2])))
                                            elif command[0] == 'Q' and len(command) >= 5:  # Quadratic curve
                                                fitz_path.append(fitz.Point(float(command[1]), float(command[2])))
                                                fitz_path.append(fitz.Point(float(command[3]), float(command[4])))
                                            else:
                                                print(f"Unexpected command format: {command}")
                                        except (IndexError, ValueError) as e:
                                            print(f"Error processing command {command}: {e}")

                                    if fitz_path:
                                        # Create a polyline annotation for FreeDraw
                                        free_draw_annot = page.add_polyline_annot(fitz_path)

                                        # Set metadata for the annotation
                                        free_draw_annot.set_info(
                                            title=annotation.get("userName", "Anurag Sable"),
                                            subject=annotation.get("subject", ""),
                                            content=id_metadata + annotation.get("content", "")
                                        )

                                        # Set appearance properties
                                        free_draw_annot.set_colors(stroke=(1, 0, 0))  # Red color
                                        free_draw_annot.set_border(width=annotation.get("strokeWidth", 2))

                                        # Finalize the annotation
                                        free_draw_annot.update()
                                    else:
                                        print(f"No valid points found for freeDraw annotation: {annotation}")
                                else:
                                    print(f"Missing path data for freeDraw annotation: {annotation}")
                            except Exception as e:
                                print(f"Error in fallback block: {e}")

                    elif annotation["type"] == "textCallout":
                        try:
                            if not annotation.get('id'):
                                annotation['id'] = f"callout_{uuid.uuid4().hex[:8]}"
                        
                            callout_id = annotation.get('id')
                            sql = """
                            IF EXISTS (SELECT 1 FROM text_callout_annotations WHERE id = ?)
                            BEGIN
                                UPDATE text_callout_annotations
                                SET document_id = ?,
                                    user_id = ?,
                                    user_name = ?,
                                    page_number = ?,
                                    text_content = ?,
                                    arrow_start_x = ?,
                                    arrow_start_y = ?,
                                    arrow_end_x = ?,
                                    arrow_end_y = ?,
                                    text_left = ?,
                                    text_top = ?,
                                    text_width = ?,
                                    text_height = ?,
                                    font_size = ?,
                                    arrow_color = ?,
                                    text_color = ?,
                                    border_color = ?
                                WHERE id = ?
                            END
                            ELSE
                            BEGIN
                                INSERT INTO text_callout_annotations (
                                    id, document_id, user_id, user_name, page_number,
                                    text_content, arrow_start_x, arrow_start_y,
                                    arrow_end_x, arrow_end_y, text_left, text_top,
                                    text_width, text_height, font_size,
                                    arrow_color, text_color, border_color
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            END
                            """

                            values = [
                                callout_id,  # For the IF EXISTS check
                                # UPDATE values
                                document_id,
                                user_id,
                                annotation.get('userName'),
                                annotation.get('page'),
                                annotation.get('text'),
                                annotation['arrowStart'][0] if 'arrowStart' in annotation else None,
                                annotation['arrowStart'][1] if 'arrowStart' in annotation else None,
                                annotation['arrowEnd'][0] if 'arrowEnd' in annotation else None,
                                annotation['arrowEnd'][1] if 'arrowEnd' in annotation else None,
                                annotation.get('textLeft'),
                                annotation.get('textTop'),
                                annotation.get('textWidth'),
                                annotation.get('textHeight'),
                                annotation.get('fontSize'),
                                annotation.get('arrowColor'),
                                annotation.get('textColor'),
                                annotation.get('borderColor'),
                                callout_id,
                                callout_id,
                                document_id,
                                user_id,
                                annotation.get('userName'),
                                annotation.get('page'),
                                annotation.get('text'),
                                annotation['arrowStart'][0] if 'arrowStart' in annotation else None,
                                annotation['arrowStart'][1] if 'arrowStart' in annotation else None,
                                annotation['arrowEnd'][0] if 'arrowEnd' in annotation else None,
                                annotation['arrowEnd'][1] if 'arrowEnd' in annotation else None,
                                annotation.get('textLeft'),
                                annotation.get('textTop'),
                                annotation.get('textWidth'),
                                annotation.get('textHeight'),
                                annotation.get('fontSize'),
                                annotation.get('arrowColor'),
                                annotation.get('textColor'),
                                annotation.get('borderColor')
                            ]
                            
                            cursor.execute(sql, values)
                            conn.commit()
                            print(f"Saved text callout annotation: {annotation.get('id')}")
                            print(f"Processing text callout annotation: {annotation}")

                            try:
                                check_query = "SELECT COUNT(*) FROM text_callout_annotations WHERE id = ?"
                                cursor.execute(check_query, [annotation.get('id')])
                                count = cursor.fetchone()[0]
                                print(f"Verification: Found {count} records with ID {annotation.get('id')}")
                            except Exception as e:
                                print(f"Error verifying saved record: {e}")


                            required_keys = ["arrowStart", "arrowEnd", "textLeft", "textTop"]
                            if not all(key in annotation for key in required_keys):
                                print("Missing required fields for textCallout annotation")
                                continue

                            annotation_metadata = f"calloutId:{callout_id};userId:{user_id};documentId:{document_id};"

                            # Extract coordinates
                            arrow_start_x, arrow_start_y = annotation["arrowStart"]
                            arrow_end_x, arrow_end_y = annotation["arrowEnd"]
                            text_left = annotation["textLeft"]
                            text_top = annotation["textTop"]
                            text_content = annotation.get("text", "")
                            
                            # Calculate text dimensions to ensure full text visibility
                            font_size = float(annotation.get("fontSize", 11) or 11)
                            # Use a temporary annotation to calculate text dimensions
                            temp_rect = fitz.Rect(0, 0, 100, 100)  # temporary rectangle
                            temp_annot = page.add_freetext_annot(
                                rect=temp_rect,
                                text=text_content,
                                fontsize=font_size,
                                fontname="Helv"
                            )
                            text_bounds = temp_annot.rect
                            page.delete_annot(temp_annot)
                            
                            # Add padding to ensure text isn't clipped
                            text_width = float(annotation["textWidth"])
                            text_height = float(annotation["textHeight"])

                            # Create the text rectangle with calculated dimensions
                            text_rect = fitz.Rect(
                                text_left, 
                                text_top, 
                                text_left + text_width,
                                text_top + text_height
                            )
                            
                            arrow_color = validate_and_normalize_color(annotation.get("arrowColor", (1, 0, 0)))
                            text_color = validate_and_normalize_color(annotation.get("textColor", (1, 0, 0)))
                            border_color = validate_and_normalize_color(annotation.get("borderColor", (1, 0, 0)))
                            
                            user_name = annotation.get("userName", "Anonymous")

                            # Define callout points
                            p1 = fitz.Point(arrow_start_x, arrow_start_y)
                            p2 = fitz.Point(arrow_end_x, arrow_end_y)
                            p3 = fitz.Point(text_left, text_top + text_height/2)

                            # Create the callout annotation with adjusted properties
                            callout_annot = page.add_freetext_annot(
                                rect=text_rect,
                                text=text_content,
                                fontsize=font_size,
                                fontname="Helv",
                                text_color=text_color,
                                fill_color=(1, 1, 1),  # White background
                                border_color=border_color,
                                callout=(p1, p2, p3),
                                line_end=fitz.PDF_ANNOT_LE_CLOSED_ARROW,
                                border_width=annotation.get("arrowWidth", 1),
                                align=0  # Left alignment
                            )

                            # Set additional properties to ensure visibility
                            callout_annot.set_flags(
                                fitz.PDF_ANNOT_IS_PRINT |  # Make it printable
                                fitz.PDF_ANNOT_IS_NO_ZOOM |  # Don't scale with zoom
                                fitz.PDF_ANNOT_IS_NO_ROTATE  # Don't rotate
                            )
                            
                            # Set metadata
                            callout_annot.set_info(
                                title=annotation_metadata,
                                subject="textCallout",
                                content= text_content
                            )

                            # callout_annot.set_text(text_content)

                            # Force update appearance
                            callout_annot.update()  # Force appearance update
                            
                            print("✅ Unified Text Callout annotation added successfully")
                            
                        except Exception as e:
                            print(f"Error adding text callout annotation: {e}")
                            traceback.print_exc()

        
                        
                except Exception as e:
                    print(f"Error processing annotation: {e}")  
                    continue

        except Exception as e:
            print(f"Database operation error: {e}")
            if conn:
                conn.rollback()
            raise

        finally:
            if conn:
                try:
                    conn.close()
                except Exception as e:
                    print(f"Error closing connection: {e}")
                

            
        output_buffer = io.BytesIO()
        pdf_document.save(output_buffer)
        pdf_document.close()
        output_buffer.seek(0)
        
        files = {
            'file': ('annotated.pdf', output_buffer, 'application/pdf')
        }
        data = {
            'DocumentId': document_id
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



#=======================================================================================
# ... existing code ...

@app.route('/api/download/annotated-pdf', methods=['POST'])
def download_annotated_pdf():
    try:
        try:
            conn = None
            # conn =get_db_connection
            conn = get_db_connection()
            if not conn:
                    raise Exception("Failed to establish database connection")
                    
            cursor = conn.cursor()

            print("Received download request")
            
            if 'file' not in request.files:
                print("No file in request")
                return jsonify({"error": "No file part"}), 400
                
            file = request.files['file']
            annotations_json = request.form.get('annotations')
            document_id = request.form.get('DocumentId')
            user_id = request.form.get('userId')

            if not document_id or not user_id:
                return jsonify({"error": "Missing DocumentId or userId"}), 400

            if not annotations_json:
                print("No annotations provided")
                return jsonify({"error": "No annotations provided"}), 400

            # Read the PDF file
            pdf_bytes = file.read()
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            annotations = json.loads(annotations_json)
            print(f"Processing {len(annotations)} annotations")

            # Process annotations (reuse your existing annotation processing code)
            for annotation in annotations:
                try:
                    page_num = int(annotation.get("page", 1))
                    if page_num <= 0:
                        page_num = 1
                    page = pdf_document[page_num - 1]  # Convert to 0-based index

                    if "documentId" not in annotation:
                        annotation["documentId"] = document_id
                    if "userId" not in annotation:
                        annotation["userId"] = user_id

                    
                    
                    print(f"Processing annotation type: {annotation['type']} on page {page_num}")

                    id_metadata = f"userId:{annotation['userId']};documentId:{annotation['documentId']};"

                    if "type" in annotation and annotation["type"] == "text" or all(key in annotation for key in ["x1", "y1", "x2", "y2", "text"]):
                        try:
                            print(f"Processing text annotation: {annotation}")
                            
                            # Create the rectangle for the text annotation
                            rect = fitz.Rect(
                                annotation["x1"], 
                                annotation["y1"], 
                                annotation["x2"], 
                                annotation["y2"]
                            )

                            annotation_text = annotation.get("content") 
                            
                            # Add the text annotation with proper parameters
                            text_annotation = page.add_freetext_annot(
                                rect=rect,
                                text=annotation_text,
                                fontsize=float(annotation.get("fontSize", 11)),
                                fontname="Helv",
                                text_color=(0, 0, 0),  # Black text
                                # fill_color=(1, 1, 1),  # White background
                                border_color=(0, 0, 0)  # Black border
                            )
                            
                            # Set metadata
                            text_annotation.set_info(
                                title=id_metadata,
                                subject=annotation.get("subject", "Text"),
                                content= annotation.get("content", annotation["text"])
                            )
                            
                            # Set border and make printable
                            text_annotation.set_border(width=0.5)
                            text_annotation.set_flags(fitz.PDF_ANNOT_IS_PRINT)
                            
                            # Update appearance
                            text_annotation.update()
                            # page.set_dirty()
                            
                            print("✅ Text annotation added successfully")
                            
                        except Exception as e:
                            print(f"Error processing text annotation: {e}")
                            traceback.print_exc()
                    
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
                                content=id_metadata + annotation.get("content", "")
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
                                content=id_metadata + annotation.get("content", "This text is highlighted.")
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
                                content=id_metadata + annotation.get("content", "This text is highlighted.")
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
                                            content=id_metadata + annotation.get("content", "This text is highlighted.")
                                        )
                                        highlight_annot.update()
                                        print(annotation)
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
                                content=id_metadata + annotation.get("content", "This text is underlined.")
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
                                content=id_metadata + annotation.get("content", "This text is underlined.")
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
                                                content=id_metadata + annotation.get("content", "This text is underlined.")
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
                                content=id_metadata + annotation.get("content", "This text has been struck out.")
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
                                content=id_metadata + annotation.get("content", "This text has been struck out.")
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
                                                content=id_metadata + annotation.get("content", "This text is struck out.")
                                            )
                                            strikeout_annot.update()
                                            print(annotation)
                                    else:
                                        print(f"Missing coordinates for line annotation: {line}")
                        else:
                            print(f"Missing coordinates for strike-out annotation: {annotation}")
                        
                    # elif annotation["type"] == "stamp":
                    #     img_src = annotation.get("imgSrc")
                    #     x1 = annotation.get("x1")
                    #     y1 = annotation.get("y1")
                    #     x2 = annotation.get("x2")
                    #     y2 = annotation.get("y2")

                    #     if img_src and x1 is not None and y1 is not None and x2 is not None and y2 is not None:
                    #         width = x2 - x1
                    #         height = y2 - y1

                    #         img_path = os.path.join(os.getcwd(), img_src.lstrip('/'))
                    #         if os.path.exists(img_path):
                    #             try:
                    #                 # Create the stamp rectangle with exact coordinates
                    #                 stamp_rect = fitz.Rect(x1, y1, x2, y2)
                                    
                    #                 # Create a stamp annotation
                    #                 stamp_annot = page.add_stamp_annot(stamp_rect)
                                    
                    #                 # Read and process the image
                    #                 with open(img_path, "rb") as img_file:
                    #                     img_data = img_file.read()
                                    
                    #                 # Set the appearance stream directly with the image data
                    #                 stamp_annot.set_appearance(stream=img_data, content=img_data)
                                    
                    #                 # Set PDF dictionary properties
                    #                 pdf_dict = stamp_annot.get_pdf_obj()
                    #                 pdf_dict.update({
                    #                     'Subtype': '/Stamp',
                    #                     'Name': '/StampAnnotation',
                    #                     'F': 4,  # Annotation flags
                    #                     'Rect': [stamp_rect.x0, stamp_rect.y0, stamp_rect.x1, stamp_rect.y1]
                    #                 })
                                    
                    #                 # Set metadata
                    #                 stamp_annot.set_info(
                    #                     title=annotation.get("userName", "Anurag Sable"),
                    #                     subject="Stamp",
                    #                     content=annotation.get("content", "This is a stamp annotation")
                    #                 )
                                    
                    #                 # Update the annotation
                    #                 stamp_annot.update()
                                    
                    #                 print(f"Stamp annotation added successfully at: {stamp_rect}")
                                    
                    #             except Exception as e:
                    #                 print(f"Error processing stamp annotation: {e}")
                    #                 print(f"Error details: {str(e)}")
                    #         else:
                    #             print(f"Image file not found: {img_path}")
                    #     else:
                    #         print("Missing required stamp annotation properties")

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
                                img_rect = fitz.Rect(x1, y1, x2, y2)  # Define the rectangle area for the stamp
                                print(f"PDF stamp insertion at: x1={x1}, y1={y1}, x2={x2}, y2={y2}, width={width}, height={height}")

                                page.insert_image(img_rect, stream=img_data, width=width, height=height)

                            # Optionally, add metadata for the stamp annotation
                            stamp_annot = page.add_text_annot(fitz.Rect(x1, y1, x2, y2), '')
                            stamp_annot.set_info(
                                title=annotation.get("userName", "Anurag Sable"),
                                subject=annotation.get("subject", "Stamp Subject"),
                                content=id_metadata + annotation.get("content", "This is a stamp annotation")
                            )
                            stamp_annot.update()

                    # elif annotation["type"] == "signature":
                    #     img_data = annotation.get("dataURL")
                    #     x1, y1 = annotation.get("x1"), annotation.get("y1")
                    #     x2, y2 = annotation.get("x2"), annotation.get("y2")

                    #     if img_data and None not in (x1, y1, x2, y2):
                    #         try:
                    #             # Decode base64 image data
                    #             if "," in img_data:
                    #                 img_bytes = base64.b64decode(img_data.split(",")[1])
                    #             else:
                    #                 img_bytes = base64.b64decode(img_data)

                    #             # Create a signature annotation
                    #             sig_rect = fitz.Rect(x1-400, y1-80, x2, y2-80)
                    #             sig_annot = page.add_stamp_annot(sig_rect)  # Use stamp annotation for signatures
                                
                    #             # Set the signature image as the appearance
                    #             sig_annot.set_appearance(stream=img_bytes, content=img_bytes)
                                
                    #             # Set metadata
                    #             sig_annot.set_info(
                    #                 title=annotation.get("userName", "Anurag Sable"),
                    #                 subject="Signature",
                    #                 content=annotation.get("content", "This is a signature annotation")
                    #             )
                    #             sig_annot.update()
                    #             print(f"Signature annotation successfully added at page {annotation.get('page')}")

                    #         except Exception as e:
                    #             print(f"Error adding signature annotation: {e}")

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
                            img_rect = fitz.Rect(x1, y1, x2, y2)

                            # Insert the image into the PDF
                            page.insert_image(img_rect, stream=io.BytesIO(img_bytes))
                            sig_annot = page.add_text_annot(fitz.Rect(x1, y1, x2, y2), '')
                            sig_annot.set_info(
                                title=annotation.get("userName", "Anurag Sable"),
                                subject=annotation.get("subject", "Signature Subject"),
                                content=id_metadata + annotation.get("content", "This is a signature annotation")
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
                                content=id_metadata + annotation.get("content", "")
                            )
                            square_annot.set_colors(stroke=[1, 0, 0])  # Red in RGB format
                            square_annot.set_border(width=annotation.get("strokeWidth", 1))
                            square_annot.update()
                            print(f"Added square annotation: {annotation}")
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
                                    content=id_metadata + annotation.get("content", "")
                                )
                                circle_annot.set_border(width=2)  # Set stroke width to 2

                                circle_annot.update()
                            else:
                                print(f"Invalid radius for circle annotation: {annotation}")
                        else:
                            print(f"Missing data for circle annotation: {annotation}")

                    elif annotation["type"] == "cloud":
                        try:
                            print("Processing cloud annotation... Block 1")
                            if "path" in annotation and isinstance(annotation["path"], list):
                                try:
                                    print("Processing cloud annotation... Block 1.1")
                                    cloud_path = annotation['path']
                                    points = []
                                    vertices = []
                                    
                                    # Convert path commands to points with better curve handling
                                    current_point = None
                                    for command in cloud_path:
                                        try:
                                            if command[0] == 'M':  # Move to
                                                current_point = fitz.Point(command[1], command[2])
                                                points.append(current_point)
                                                vertices.append(current_point)
                                            elif command[0] == 'L':  # Line to
                                                current_point = fitz.Point(command[1], command[2])
                                                points.append(current_point)
                                                vertices.append(current_point)
                                            elif command[0] == 'C':  # Cubic bezier curve
                                                start = current_point
                                                c1 = fitz.Point(command[1], command[2])
                                                c2 = fitz.Point(command[3], command[4])
                                                end = fitz.Point(command[5], command[6])
                                                
                                                steps = 10
                                                for i in range(1, steps + 1):
                                                    t = i / steps
                                                    x = (1-t)**3 * start.x + 3*(1-t)**2 * t * c1.x + 3*(1-t) * t**2 * c2.x + t**3 * end.x
                                                    y = (1-t)**3 * start.y + 3*(1-t)**2 * t * c1.y + 3*(1-t) * t**2 * c2.y + t**3 * end.y
                                                    point = fitz.Point(x, y)
                                                    points.append(point)
                                                    vertices.append(point)
                                                current_point = end
                                        except Exception as e:
                                            print(f"Error processing command: {e}")
                                            continue

                                    print(f"Total points generated: {len(points)}")
                                    if points:
                                        try:
                                            cloud_annot = page.add_polyline_annot(points)
                                            cloud_annot.set_border(width=annotation.get("strokeWidth", 2))
                                            cloud_annot.set_colors(stroke=(1, 0, 0))  # Red color
                                            cloud_annot.set_info(
                                                title=annotation.get("userName", "Anurag Sable"),
                                                subject="Cloud",
                                                content=id_metadata + annotation.get("content", "")
                                            )

                                            if points[0] != points[-1]:
                                                points.append(points[0])
                                                vertices.append(vertices[0])

                                            cloud_annot.update()
                                            print(annotation)
                                            print(f"Cloud annotation added successfully")
                                        except Exception as e:
                                            print(f"Error creating cloud annotation: {e}")
                                    else:
                                        print("No valid points generated for cloud annotation")
                                except Exception as e:
                                    print(f"Error processing cloud path: {e}")
                                    raise  # Re-raise to trigger fallback
                            else:
                                raise ValueError("Invalid path format")  # Trigger fallback method

                        except Exception as e:
                            print(f"Error in first block cloud 1: {e}. Trying fallback method.")

                            try:
                                print("Using fallback method... Block 2")
                                if "path" in annotation:
                                    try:
                                        path = annotation["path"].split(' ')
                                        points = []
                                        vertices = []

                                        # Parse the path string into points
                                        for i in range(0, len(path), 3):
                                            try:
                                                command = path[i]
                                                if command == 'M' or command == 'L':
                                                    x = float(path[i + 1])
                                                    y = float(path[i + 2])
                                                    point = fitz.Point(x, y)
                                                    points.append(point)
                                                    vertices.append(point)
                                            except Exception as e:
                                                print(f"Error processing fallback command: {e}")
                                                continue

                                        print(f"Fallback: Total points generated: {len(points)}")
                                        if points:
                                            try:
                                                cloud_annot = page.add_polyline_annot(points)
                                                cloud_annot.set_border(width=annotation.get("strokeWidth", 2))
                                                cloud_annot.set_colors(stroke=(1, 0, 0))  # Red color
                                                cloud_annot.set_info(
                                                    title=annotation.get("userName", "Anurag Sable"),
                                                    subject="Cloud",
                                                    content=id_metadata + annotation.get("content", "")
                                                )

                                                if points[0] != points[-1]:
                                                    points.append(points[0])
                                                    vertices.append(vertices[0])

                                                cloud_annot.update()
                                                print(f"Cloud annotation added successfully (fallback method)")
                                            except Exception as e:
                                                print(f"Error creating cloud annotation in fallback: {e}")
                                        else:
                                            print("No valid points generated in fallback method")
                                    except Exception as e:
                                        print(f"Error processing fallback path: {e}")
                                else:
                                    print("No path data available for fallback method")
                            except Exception as e:
                                print(f"Error in fallback block cloud: {e}")
                    # elif annotation["type"] == "cloud":
                    #     if "path" in annotation and isinstance(annotation["path"], list):
                    #         cloud_path = annotation['path']
                    #         points = []
                    #         for command in cloud_path:
                    #             if command[0] == 'M':
                    #                 points.append(fitz.Point(command[1], command[2]))
                    #             elif command[0] == 'L':
                    #                 points.append(fitz.Point(command[1], command[2]))
                    #             elif command[0] == 'C':
                    #                 points.append(fitz.Point(command[1], command[2]))
                    #                 points.append(fitz.Point(command[3], command[4]))
                    #                 points.append(fitz.Point(command[5], command[6]))
                    #         try:
                    #             cloud_annot = page.add_polyline_annot(points)
                    #             cloud_annot.set_info(
                    #                 title=annotation.get("userName", "Anurag Sable"),
                    #                 subject=annotation.get("subject", "Cloud"),
                    #                 content=annotation.get("content", "")
                    #            )
                    #             page.draw_polyline(
                    #                 points,
                    #                 color=(1, 0, 0),
                    #                 width=annotation.get("strokeWidth", 2),
                    #                 closePath=True
                    #             )
                    #         except Exception as e:
                    #             print(f"Error drawing cloud annotation: {e}")
                    #     else:
                    #         print(f"Missing path data for cloud annotation: {annotation}")

                    elif annotation["type"] == "freeDraw":
                        try:
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
                                    content=id_metadata + annotation.get("content", "")
                                )

                                # Set appearance properties
                                free_draw_annot.set_colors(stroke=(1, 0, 0))  # Red color
                                free_draw_annot.set_border(width=annotation.get("strokeWidth", 2))

                                # Finalize the annotation
                                free_draw_annot.update()
                                print(f"FreeDraw annotation added successfully {annotation}")
                        except Exception as e:
                            print(f"Error in first block: {e}. Trying fallback method.")
                            
                            try:
                                if "path" in annotation:
                                    path = annotation["path"]
                                    fitz_path = []

                                    # Convert path string to a list of commands
                                    if isinstance(path, str):
                                        path = path.split(' ')

                                    # Ensure path is a list of commands
                                    for i in range(0, len(path), 3):
                                        try:
                                            command = path[i:i+3]
                                            if command[0] == 'M' and len(command) >= 3:  # Move to
                                                fitz_path.append(fitz.Point(float(command[1]), float(command[2])))
                                            elif command[0] == 'L' and len(command) >= 3:  # Line to
                                                fitz_path.append(fitz.Point(float(command[1]), float(command[2])))
                                            elif command[0] == 'Q' and len(command) >= 5:  # Quadratic curve
                                                fitz_path.append(fitz.Point(float(command[1]), float(command[2])))
                                                fitz_path.append(fitz.Point(float(command[3]), float(command[4])))
                                            else:
                                                print(f"Unexpected command format: {command}")
                                        except (IndexError, ValueError) as e:
                                            print(f"Error processing command {command}: {e}")

                                    if fitz_path:
                                        # Create a polyline annotation for FreeDraw
                                        free_draw_annot = page.add_polyline_annot(fitz_path)

                                        # Set metadata for the annotation
                                        free_draw_annot.set_info(
                                            title=annotation.get("userName", "Anurag Sable"),
                                            subject=annotation.get("subject", ""),
                                            content=id_metadata + annotation.get("content", "")
                                        )

                                        # Set appearance properties
                                        free_draw_annot.set_colors(stroke=(1, 0, 0))  # Red color
                                        free_draw_annot.set_border(width=annotation.get("strokeWidth", 2))

                                        # Finalize the annotation
                                        free_draw_annot.update()
                                        print(f"FreeDraw annotation added successfully {annotation}")   
                                    else:
                                        print(f"No valid points found for freeDraw annotation: {annotation}")
                                else:
                                    print(f"Missing path data for freeDraw annotation: {annotation}")
                            except Exception as e:
                                print(f"Error in fallback block: {e}")

                    elif annotation["type"] == "textCallout":
                        try:
                            if not annotation.get('id'):
                                annotation['id'] = f"callout_{uuid.uuid4().hex[:8]}"
                        
                            callout_id = annotation.get('id')
                            sql = """
                            IF EXISTS (SELECT 1 FROM text_callout_annotations WHERE id = ?)
                            BEGIN
                                UPDATE text_callout_annotations
                                SET document_id = ?,
                                    user_id = ?,
                                    user_name = ?,
                                    page_number = ?,
                                    text_content = ?,
                                    arrow_start_x = ?,
                                    arrow_start_y = ?,
                                    arrow_end_x = ?,
                                    arrow_end_y = ?,
                                    text_left = ?,
                                    text_top = ?,
                                    text_width = ?,
                                    text_height = ?,
                                    font_size = ?,
                                    arrow_color = ?,
                                    text_color = ?,
                                    border_color = ?
                                WHERE id = ?
                            END
                            ELSE
                            BEGIN
                                INSERT INTO text_callout_annotations (
                                    id, document_id, user_id, user_name, page_number,
                                    text_content, arrow_start_x, arrow_start_y,
                                    arrow_end_x, arrow_end_y, text_left, text_top,
                                    text_width, text_height, font_size,
                                    arrow_color, text_color, border_color
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            END
                            """

                            values = [
                                callout_id,  # For the IF EXISTS check
                                # UPDATE values
                                document_id,
                                user_id,
                                annotation.get('userName'),
                                annotation.get('page'),
                                annotation.get('text'),
                                annotation['arrowStart'][0] if 'arrowStart' in annotation else None,
                                annotation['arrowStart'][1] if 'arrowStart' in annotation else None,
                                annotation['arrowEnd'][0] if 'arrowEnd' in annotation else None,
                                annotation['arrowEnd'][1] if 'arrowEnd' in annotation else None,
                                annotation.get('textLeft'),
                                annotation.get('textTop'),
                                annotation.get('textWidth'),
                                annotation.get('textHeight'),
                                annotation.get('fontSize'),
                                annotation.get('arrowColor'),
                                annotation.get('textColor'),
                                annotation.get('borderColor'),
                                callout_id,
                                callout_id,
                                document_id,
                                user_id,
                                annotation.get('userName'),
                                annotation.get('page'),
                                annotation.get('text'),
                                annotation['arrowStart'][0] if 'arrowStart' in annotation else None,
                                annotation['arrowStart'][1] if 'arrowStart' in annotation else None,
                                annotation['arrowEnd'][0] if 'arrowEnd' in annotation else None,
                                annotation['arrowEnd'][1] if 'arrowEnd' in annotation else None,
                                annotation.get('textLeft'),
                                annotation.get('textTop'),
                                annotation.get('textWidth'),
                                annotation.get('textHeight'),
                                annotation.get('fontSize'),
                                annotation.get('arrowColor'),
                                annotation.get('textColor'),
                                annotation.get('borderColor')
                            ]
                            
                            cursor.execute(sql, values)
                            conn.commit()
                            print(f"Saved text callout annotation: {annotation.get('id')}")
                            print(f"Processing text callout annotation: {annotation}")

                            try:
                                check_query = "SELECT COUNT(*) FROM text_callout_annotations WHERE id = ?"
                                cursor.execute(check_query, [annotation.get('id')])
                                count = cursor.fetchone()[0]
                                print(f"Verification: Found {count} records with ID {annotation.get('id')}")
                            except Exception as e:
                                print(f"Error verifying saved record: {e}")


                            required_keys = ["arrowStart", "arrowEnd", "textLeft", "textTop"]
                            if not all(key in annotation for key in required_keys):
                                print("Missing required fields for textCallout annotation")
                                continue

                            annotation_metadata = f"calloutId:{callout_id};userId:{user_id};documentId:{document_id};"

                            # Extract coordinates
                            arrow_start_x, arrow_start_y = annotation["arrowStart"]
                            arrow_end_x, arrow_end_y = annotation["arrowEnd"]
                            text_left = annotation["textLeft"]
                            text_top = annotation["textTop"]
                            text_content = annotation.get("text", "")
                            
                            # Calculate text dimensions to ensure full text visibility
                            font_size = float(annotation.get("fontSize", 11) or 11)
                            # Use a temporary annotation to calculate text dimensions
                            temp_rect = fitz.Rect(0, 0, 100, 100)  # temporary rectangle
                            temp_annot = page.add_freetext_annot(
                                rect=temp_rect,
                                text=text_content,
                                fontsize=font_size,
                                fontname="Helv"
                            )
                            text_bounds = temp_annot.rect
                            page.delete_annot(temp_annot)
                            
                            # Add padding to ensure text isn't clipped
                            text_width = float(annotation["textWidth"])
                            text_height = float(annotation["textHeight"])

                            # Create the text rectangle with calculated dimensions
                            text_rect = fitz.Rect(
                                text_left, 
                                text_top, 
                                text_left + text_width,
                                text_top + text_height
                            )
                            
                            arrow_color = validate_and_normalize_color(annotation.get("arrowColor", (1, 0, 0)))
                            text_color = validate_and_normalize_color(annotation.get("textColor", (1, 0, 0)))
                            border_color = validate_and_normalize_color(annotation.get("borderColor", (1, 0, 0)))
                            
                            user_name = annotation.get("userName", "Anonymous")

                            # Define callout points
                            p1 = fitz.Point(arrow_start_x, arrow_start_y)
                            p2 = fitz.Point(arrow_end_x, arrow_end_y)
                            p3 = fitz.Point(text_left, text_top + text_height/2)

                            # Create the callout annotation with adjusted properties
                            callout_annot = page.add_freetext_annot(
                                rect=text_rect,
                                text=text_content,
                                fontsize=font_size,
                                fontname="Helv",
                                text_color=text_color,
                                fill_color=(1, 1, 1),  # White background
                                border_color=border_color,
                                callout=(p1, p2, p3),
                                line_end=fitz.PDF_ANNOT_LE_CLOSED_ARROW,
                                border_width=annotation.get("arrowWidth", 1),
                                align=0  # Left alignment
                            )

                            # Set additional properties to ensure visibility
                            callout_annot.set_flags(
                                fitz.PDF_ANNOT_IS_PRINT |  # Make it printable
                                fitz.PDF_ANNOT_IS_NO_ZOOM |  # Don't scale with zoom
                                fitz.PDF_ANNOT_IS_NO_ROTATE  # Don't rotate
                            )
                            
                            # Set metadata
                            callout_annot.set_info(
                                title=annotation_metadata,
                                subject="textCallout",
                                content= text_content
                            )

                            # callout_annot.set_text(text_content)

                            # Force update appearance
                            callout_annot.update()  # Force appearance update
                            
                            print("✅ Unified Text Callout annotation added successfully")
                            
                        except Exception as e:
                            print(f"Error adding text callout annotation: {e}")
                            traceback.print_exc()

        
                        
                except Exception as e:
                    print(f"Error processing annotation: {e}")  
                    continue

        except Exception as e:
            print(f"Database operation error: {e}")
            if conn:
                conn.rollback()
            raise

        finally:
            if conn:
                try:
                    conn.close()
                except Exception as e:
                    print(f"Error closing connection: {e}")    


        #     for page_num in processed_pages:
        #         page = pdf_document.load_page(page_num)
        #         page.apply_transform_matrix(fitz.Matrix(1, 0, 0, 1, 0, 0))

        # # Force commit all changes before final save
        #     pdf_document.save_incremental()

        # Save to memory buffer
        output_buffer = io.BytesIO()
        pdf_document.save(output_buffer)
        pdf_document.close()
        output_buffer.seek(0)

        # Return the PDF file as a download
        return send_file(
            output_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='annotated_document.pdf'
        )

    except Exception as e:
        print(f"Error in download_annotated_pdf: {str(e)}")
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500

#=======================================================================================

@app.route('/api/debug/extract-callouts', methods=['POST'])
def debug_extract_callouts():
    try:
        data = request.json
        url = data.get('url')
        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        # Download the PDF
        response = requests.get(url)
        if not response.ok:
            return jsonify({'error': 'Failed to download PDF'}), 400

        # Create a temporary file to work with
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file.write(response.content)
            tmp_path = tmp_file.name

        # Open the PDF with PyMuPDF
        doc = fitz.open(tmp_path)
        callout_details = []
        
        # Extract callout annotations only
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            for annot in page.annots():
                # Focus only on callouts
                subject = annot.info.get('subject', '')
                
                if subject == 'textCallout' or annot.type[1].lower() == 'freetext':
                    # Basic annotation properties
                    annot_info = {
                        'type': annot.type,
                        'rect': [annot.rect.x0, annot.rect.y0, annot.rect.x1, annot.rect.y1],
                        'page': page_num + 1,
                        'content': annot.info.get('content', ''),
                        'title': annot.info.get('title', ''),
                        'subject': subject
                    }
                    
                    # Try to extract callout points
                    try:
                        if hasattr(annot, 'callout'):
                            callout_points = annot.callout
                            if callout_points:
                                annot_info['callout_points'] = [
                                    [p.x, p.y] for p in callout_points
                                ]
                    except Exception as e:
                        annot_info['callout_error'] = str(e)
                    
                    # Get color information
                    if hasattr(annot, 'colors'):
                        annot_info['colors'] = annot.colors
                    
                    # Get border information
                    if hasattr(annot, 'border'):
                        annot_info['border'] = annot.border
                    
                    callout_details.append(annot_info)
        
        # Clean up
        doc.close()
        os.unlink(tmp_path)
        
        return jsonify({
            'callout_count': len(callout_details),
            'callout_details': callout_details
        })
        
    except Exception as e:
        print(f"Error debugging callouts: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def get_db_connection():
    try:
        conn = pyodbc.connect(
            'DRIVER={SQL Server};'
            'SERVER=DESKTOP-EHPE93D\\SQLEXPRESS;'  # Usually looks like this for local SQL Server Express
            'DATABASE=PDFAnnotations;'
            'Trusted_Connection=yes;'  # Use this for Windows Authentication
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise Exception(f"Database connection failed: {e}")



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

@app.route('/check_links_result', methods=['POST'])
def handle_check_links_result():
    try:
        data = request.json
        result = data.get('result', False)
        
        app.config['USE_MERGE_FUNCTION'] = result
        
        print(f"Received check_links_result: {result}. Will use {'extract_annotations_merge' if result else 'extract_annotations'}")
        
        return jsonify({
            'success': True,
            'message': f"Function selection set to {'extract_annotations_merge' if result else 'extract_annotations'}"
        })
    except Exception as e:
        print(f"Error handling check_links_result: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/annotations/extract', methods=['POST'])
def route_annotations_extract():
    if app.config.get('USE_MERGE_FUNCTION', False):
        print("Using extract_annotations_merge function")
        return extract_annotations_merge()
    else:
        print("Using extract_annotations function")
        return extract_annotations()

# @app.route('/api/annotations/extract', methods=['POST'])
def extract_annotations():
    try:
        # result, error = extract_annotations_from_local_files()
        # if result is not None:
        #     return jsonify(result)
        
        # print(f"Local file extraction failed or no local files found: {error}")
        
        data = request.json
        url = data.get('url')
        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        # Download the PDF
        response = requests.get(url)
        if not response.ok:
            return jsonify({'error': 'Failed to download PDF'}), 400

        # Create a temporary file to work with
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file.write(response.content)
            tmp_path = tmp_file.name

        # Open the PDF with PyMuPDF
        doc = fitz.open(tmp_path)
        annotations_by_page = {}
        
        # Extract annotations from each page
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_annotations = []
            
            for annot in page.annots():

                annotation_type = annot.type[1].lower()  # Remove leading '/'
                # Convert 'freetext' to 'text' type
                if annotation_type == 'freetext':
                    annotation_type = 'text'
                # Get basic annotation data
                annotation_data = {
                    'id': str(uuid.uuid4()),
                    'type': annotation_type,  # Remove leading '/'
                    'page': page_num + 1,
                    'content': annot.info.get('content', ''),
                    'userName': annot.info.get('title', 'Unknown'),
                    'createdAt': datetime.now().isoformat()
                }
                title = annot.info.get('title', '')
                content = annot.info.get('content', '')

                if annotation_type == 'text':
                    # Try to extract userId from title first
                    user_id_match = re.search(r'userId:([^;]+)', title)
                    if user_id_match:
                        annotation_data['userId'] = user_id_match.group(1)
                        print(f"Found user ID in title for text annotation: {annotation_data['userId']}")
                    
                    # Try to extract documentId from title
                    doc_id_match = re.search(r'documentId:([^;]+)', title)
                    if doc_id_match:
                        annotation_data['documentId'] = doc_id_match.group(1)
                        print(f"Found document ID in title for text annotation: {annotation_data['documentId']}")

                # If not found in title or not a text annotation, check content
                if 'userId' not in annotation_data:
                    user_id_match = re.search(r'userId:([^;]+)', content)
                    if user_id_match:
                        annotation_data['userId'] = user_id_match.group(1)
                        content = re.sub(r'userId:[^;]+;', '', content)
                
                if 'documentId' not in annotation_data:
                    doc_id_match = re.search(r'documentId:([^;]+)', content)
                    if doc_id_match:
                        annotation_data['documentId'] = doc_id_match.group(1)
                        content = re.sub(r'documentId:[^;]+;', '', content)
                annotation_data['content'] = content.strip()
                

                user_id_match = re.search(r'userId:([^;]+)', content)
                if user_id_match:
                    annotation_data['userId'] = user_id_match.group(1)
                    # Remove the userId part from the content to display clean content to user
                    content = re.sub(r'userId:[^;]+;', '', content)
                
                # Look for documentId in the content
                doc_id_match = re.search(r'documentId:([^;]+)', content)
                if doc_id_match:
                    annotation_data['documentId'] = doc_id_match.group(1)
                    # Remove the documentId part from the content to display clean content to user
                    content = re.sub(r'documentId:[^;]+;', '', content)
                
                # Update content with cleaned version (without IDs)
                annotation_data['content'] = content.strip()

                # Get annotation rectangle
                rect = annot.rect
                
                # Skip invalid rectangles (sometimes seen with text annotations)
                if rect.x0 < -1000000 or rect.y0 < -1000000:
                    print(f"Skipping annotation with invalid rectangle: {annotation_data['type']}")
                    continue
                
                annotation_data.update({
                    'x1': rect.x0,
                    'y1': rect.y0,
                    'x2': rect.x1,
                    'y2': rect.y1,
                    'width': rect.width,
                    'height': rect.height
                })
                subject = annot.info.get('subject', '')
                # In your extract_annotations function:
                if subject == 'textCallout':
                    annotation_data['type'] = 'textCallout'
                    rect = annot.rect
                    
                    # Get the title and extract metadata from it FIRST
                    title = annot.info.get('title', '')
                    
                    # Extract calloutId early to use for database lookup
                    callout_id_match = re.search(r'calloutId:([^;]+)', title)
                    if callout_id_match:
                        annotation_data['id'] = callout_id_match.group(1)
                        print(f"Found callout ID in title: {annotation_data['id']}")
                        
                        # Immediately try to get position from database using the found ID
                        try:
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            
                            db_query = """
                            SELECT text_left, text_top 
                            FROM text_callout_annotations 
                            WHERE id = ?
                            """
                            cursor.execute(db_query, [annotation_data['id']])
                            row = cursor.fetchone()

                            if row and row[0] is not None and row[1] is not None:
                                # Use exact database values
                                annotation_data['textLeft'] = float(row[0])  # This should be 352.161047813567
                                annotation_data['textTop'] = float(row[1])   # This should be 125.117486889766
                                print(f"Using database position - Left: {row[0]}, Top: {row[1]}")
                            else:
                                print("No database position found, using PDF coordinates")
                                annotation_data['textLeft'] = float(rect.x0)
                                annotation_data['textTop'] = float(rect.y0)
                            
                            conn.close()
                        except Exception as e:
                            print(f"Database error retrieving text position: {e}")
                            traceback.print_exc()
                            annotation_data['textLeft'] = float(rect.x0)
                            annotation_data['textTop'] = float(rect.y0)
                    else:
                        # No ID found, use PDF coordinates
                        annotation_data['textLeft'] = float(rect.x0)
                        annotation_data['textTop'] = float(rect.y0)
                    
                    # Set fixed dimensions
                    annotation_data['textWidth'] = 75
                    annotation_data['textHeight'] = 14.69

                    # Remove rectangle coordinates
                    annotation_data.pop('x1', None)
                    annotation_data.pop('y1', None)
                    annotation_data.pop('x2', None)
                    annotation_data.pop('y2', None)
                    annotation_data.pop('width', None)
                    annotation_data.pop('height', None)

                    # Rest of your existing code...
                    # Extract the actual text content (cleaned of metadata)
                    raw_content = annot.info.get('content', '')
                    cleaned_content = re.sub(r'(userId|documentId|calloutId):[^;]+;', '', raw_content).strip()
                    annotation_data['text'] = cleaned_content
                    
                    # Get the title and extract metadata from it
                    title = annot.info.get('title', '')
                    
                    # Extract calloutId, userId, documentId from title
                    callout_id_match = re.search(r'calloutId:([^;]+)', title)
                    if callout_id_match:
                        annotation_data['id'] = callout_id_match.group(1)
                        print(f"Found callout ID in title: {annotation_data['id']}")
                    
                    user_id_match = re.search(r'userId:([^;]+)', title)
                    if user_id_match:
                        annotation_data['userId'] = user_id_match.group(1)
                        print(f"Found user ID in title: {annotation_data['userId']}")
                    
                    doc_id_match = re.search(r'documentId:([^;]+)', title)
                    if doc_id_match:
                        annotation_data['documentId'] = doc_id_match.group(1)
                        print(f"Found document ID in title: {annotation_data['documentId']}")
                    
                    # Clean up the userName field if it contains metadata
                    user_name = annotation_data.get('userName', '')
                    if user_name and (user_name.startswith('userId:') or ';' in user_name):
                        # Try to extract a real username from elsewhere or set a default
                        annotation_data['userName'] = "Anurag Sable"  # Default fallback
                    
                    # IMPORTANT: Extract arrow coordinates from the PDF annotation
                    # PyMuPDF stores callout line information in the annotation
                    if hasattr(annot, 'callout'):
                        try:
                            callout_points = annot.callout
                            if callout_points and len(callout_points) >= 3:
                                # First point is typically the arrow start
                                annotation_data['arrowStart'] = [callout_points[0].x, callout_points[0].y]
                                # Second point is the arrow end / text connection point
                                annotation_data['arrowEnd'] = [callout_points[1].x, callout_points[1].y]
                                print(f"Extracted arrow points from PDF: start={annotation_data['arrowStart']}, end={annotation_data['arrowEnd']}")
                        except Exception as e:
                            print(f"Error extracting callout points: {e}")
                    
                    # If we have an ID, try to get data from database as backup
                    if 'id' in annotation_data:
                        try:
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            
                            # Query the database for this callout
                            db_query = "SELECT * FROM text_callout_annotations WHERE id = ?"
                            cursor.execute(db_query, [annotation_data['id']])
                            row = cursor.fetchone()
                            
                            if row:
                                # Found matching record in database
                                columns = [column[0] for column in cursor.description]
                                db_data = dict(zip(columns, row))
                                
                                print(f"Database record found: {db_data}")
                                
                                # Set arrowStart and arrowEnd from database if not already set
                                if ('arrowStart' not in annotation_data or not annotation_data['arrowStart']) and \
                                db_data.get('arrow_start_x') is not None and db_data.get('arrow_start_y') is not None:
                                    annotation_data['arrowStart'] = [db_data['arrow_start_x'], db_data['arrow_start_y']]
                                    print(f"Using arrow start from database: {annotation_data['arrowStart']}")
                                
                                if ('arrowEnd' not in annotation_data or not annotation_data['arrowEnd']) and \
                                db_data.get('arrow_end_x') is not None and db_data.get('arrow_end_y') is not None:
                                    annotation_data['arrowEnd'] = [db_data['arrow_end_x'], db_data['arrow_end_y']]
                                    print(f"Using arrow end from database: {annotation_data['arrowEnd']}")
                                
                                # Get other fields if needed
                                if db_data.get('user_name') and not annotation_data.get('userName', '').strip():
                                    annotation_data['userName'] = db_data['user_name']
                                
                                if db_data.get('text_content') and not annotation_data.get('text', '').strip():
                                    annotation_data['text'] = db_data['text_content']
                                
                                if db_data.get('font_size') and not annotation_data.get('fontSize'):
                                    annotation_data['fontSize'] = db_data['font_size']
                                
                                # Map other fields
                                field_mappings = {
                                    'arrow_color': 'arrowColor',
                                    'text_color': 'textColor',
                                    'border_color': 'borderColor'
                                }
                                
                                for db_field, annot_field in field_mappings.items():
                                    if db_field in db_data and db_data[db_field] and annot_field not in annotation_data:
                                        annotation_data[annot_field] = db_data[db_field]
                            else:
                                print(f"No database record found for callout ID: {annotation_data['id']}")
                            
                            conn.close()
                        except Exception as e:
                            print(f"Database error retrieving callout: {e}")
                            traceback.print_exc()
                    
                    # Ensure we have required fields with defaults if needed
                    if 'arrowStart' not in annotation_data or not annotation_data['arrowStart']:
                        # Default arrow start if not found (left of text box)
                        annotation_data['arrowStart'] = [rect.x0 - 50, rect.y0 + rect.height/2]
                        print(f"Using default arrowStart: {annotation_data['arrowStart']}")
                    
                    if 'arrowEnd' not in annotation_data or not annotation_data['arrowEnd']:
                        # Default arrow end (left edge of text box)
                        annotation_data['arrowEnd'] = [rect.x0, rect.y0 + rect.height/2]
                        print(f"Using default arrowEnd: {annotation_data['arrowEnd']}")
                    
                    if 'textColor' not in annotation_data:
                        annotation_data['textColor'] = 'red'
                    
                    if 'arrowColor' not in annotation_data:
                        annotation_data['arrowColor'] = 'red'
                    
                    if 'borderColor' not in annotation_data:
                        annotation_data['borderColor'] = 'red'

                
                        

                content = annot.info.get('content', '')


                # Handle specific annotation types
                if annotation_data['type'] == 'polyline':
                    # Get vertices for polyline
                    vertices = annot.vertices
                    if vertices:
                        # Convert tuple vertices to dict with x, y coordinates
                        annotation_data['points'] = [
                            {'x': vertex[0], 'y': vertex[1]} 
                            for vertex in vertices
                        ]
                        
                        # Also update the path for fabric.js
                        points = annotation_data['points']
                        if points:
                            path = f"M {points[0]['x']} {points[0]['y']}"
                            for point in points[1:]:
                                path += f" L {point['x']} {point['y']}"
                            annotation_data['path'] = path

                        # Determine if it's a cloud or freeDraw based on content or shape characteristics
                        content_lower = annotation_data['content'].lower()
                        subject_lower = annot.info.get('subject', '').lower()
                        
                        # Check for cloud annotation by content or subject
                        if "cloud" in content_lower or "cloud" in subject_lower:
                            annotation_data['type'] = 'cloud'
                            print(f"Identified cloud annotation from content: {annotation_data['id']}")
                        
                        # Check for freeDraw annotation based on content
                        elif any(term in content_lower for term in ["freedraw", "free draw"]) or any(term in subject_lower for term in ["freedraw", "free draw"]):
                            annotation_data['type'] = 'freeDraw'
                            print(f"Identified freeDraw annotation from content: {annotation_data['id']}")
                        
                        # If not identified by content, analyze shape characteristics
                        else:
                            # Calculate the area of the bounding box
                            area = rect.width * rect.height
                            
                            # Calculate the perimeter of the shape
                            perimeter = 0
                            for i in range(len(points)-1):
                                dx = points[i+1]['x'] - points[i]['x']
                                dy = points[i+1]['y'] - points[i]['y']
                                perimeter += (dx**2 + dy**2)**0.5
                            
                            # Check if the shape is closed
                            first_point = points[0]
                            last_point = points[-1]
                            dx = last_point['x'] - first_point['x']
                            dy = last_point['y'] - first_point['y']
                            is_closed = (dx**2 + dy**2)**0.5 < 20  # Threshold for "closedness"
                            
                            # Cloud detection - closed shape with reasonable perimeter-to-area ratio
                            if area > 0 and is_closed and perimeter / area < 0.5:
                                annotation_data['type'] = 'cloud'
                                print(f"Identified cloud annotation from shape analysis: {annotation_data['id']}")
                            # FreeDraw detection - many vertices or high perimeter-to-area ratio
                            elif len(vertices) > 30 or (area > 0 and perimeter / area > 1.0):
                                annotation_data['type'] = 'freeDraw'
                                print(f"Identified freeDraw annotation from analysis: {annotation_data['id']}")
                        
                        # For debugging
                        print(f"Annotation type: {annotation_data['type']}, Vertices: {len(vertices)}, Content: '{content_lower}'")
                
                elif annotation_data['type'] == 'text':
                    # Handle text annotations - ensure they have valid coordinates
                    # If coordinates are invalid, set reasonable defaults
                    if annotation_data['x1'] < 0 or annotation_data['y1'] < 0:
                        # Set default position in the center of the page
                        page_rect = page.rect
                        annotation_data.update({
                            'x1': page_rect.width / 2,
                            'y1': page_rect.height / 2,
                            'x2': page_rect.width / 2 + 100,  # Default width of 100
                            'y2': page_rect.height / 2 + 50,  # Default height of 50
                            'width': 100,
                            'height': 50
                        })
                    
                    # Skip text annotations with empty content
                    if not annotation_data['content'].strip():
                        print(f"Skipping text annotation with empty content: {annotation_data['id']}")
                        continue
                
                elif annotation_data['type'] in ['highlight', 'underline', 'strikeout']:
                    annotation_data['lineAnnotations'] = [{
                        'left': rect.x0,
                        'top': rect.y0,
                        'width': rect.width,
                        'height': rect.height
                    }]

                # Add stroke color and width if available
                if hasattr(annot, 'colors'):
                    stroke_color = annot.colors.get('stroke')
                    if stroke_color:
                        annotation_data['stroke'] = f'rgb({int(stroke_color[0]*255)}, {int(stroke_color[1]*255)}, {int(stroke_color[2]*255)})'
                
                if hasattr(annot, 'border'):
                    annotation_data['strokeWidth'] = annot.border.get('width', 1)

                # Add default stroke color if none is set
                if 'stroke' not in annotation_data:
                    annotation_data['stroke'] = 'rgb(255, 0, 0)'  # Default red color

                page_annotations.append(annotation_data)
            
            if page_annotations:
                annotations_by_page[str(page_num + 1)] = page_annotations

        # Create a clean PDF without annotations
        clean_doc = fitz.open(tmp_path)
        for page in clean_doc:
            for annot in page.annots():
                page.delete_annot(annot)

        # Save clean PDF to memory
        clean_pdf_bytes = clean_doc.write()
        clean_pdf_base64 = base64.b64encode(clean_pdf_bytes).decode('utf-8')

        # Clean up
        doc.close()
        clean_doc.close()
        os.unlink(tmp_path)

        print("Extracted annotations:", annotations_by_page)  

        return jsonify({
            'annotations': annotations_by_page,
            'cleanPdfContent': clean_pdf_base64,
            'message': 'Annotations extracted successfully'
        })

    except Exception as e:
        print(f"Error extracting annotations: {str(e)}")  
        import traceback
        traceback.print_exc()  
        return jsonify({'error': str(e)}), 500




# @app.route('/api/annotations/extract', methods=['POST'])
def extract_annotations_merge():
    try:
        result, error = extract_annotations_from_local_files()
        if result is not None:
            return jsonify(result)
        
        print(f"Local file extraction failed or no local files found: {error}")
        
        data = request.json
        url = data.get('url')
        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        # Download the PDF
        response = requests.get(url)
        if not response.ok:
            return jsonify({'error': 'Failed to download PDF'}), 400

        # Create a temporary file to work with
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file.write(response.content)
            tmp_path = tmp_file.name

        # Open the PDF with PyMuPDF
        doc = fitz.open(tmp_path)
        annotations_by_page = {}
        
        # Extract annotations from each page
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_annotations = []
            
            for annot in page.annots():

                annotation_type = annot.type[1].lower()  # Remove leading '/'
                # Convert 'freetext' to 'text' type
                if annotation_type == 'freetext':
                    annotation_type = 'text'
                # Get basic annotation data
                annotation_data = {
                    'id': str(uuid.uuid4()),
                    'type': annotation_type,  # Remove leading '/'
                    'page': page_num + 1,
                    'content': annot.info.get('content', ''),
                    'userName': annot.info.get('title', 'Unknown'),
                    'createdAt': datetime.now().isoformat()
                }
                title = annot.info.get('title', '')
                content = annot.info.get('content', '')

                if annotation_type == 'text':
                    # Try to extract userId from title first
                    user_id_match = re.search(r'userId:([^;]+)', title)
                    if user_id_match:
                        annotation_data['userId'] = user_id_match.group(1)
                        print(f"Found user ID in title for text annotation: {annotation_data['userId']}")
                    
                    # Try to extract documentId from title
                    doc_id_match = re.search(r'documentId:([^;]+)', title)
                    if doc_id_match:
                        annotation_data['documentId'] = doc_id_match.group(1)
                        print(f"Found document ID in title for text annotation: {annotation_data['documentId']}")

                # If not found in title or not a text annotation, check content
                if 'userId' not in annotation_data:
                    user_id_match = re.search(r'userId:([^;]+)', content)
                    if user_id_match:
                        annotation_data['userId'] = user_id_match.group(1)
                        content = re.sub(r'userId:[^;]+;', '', content)
                
                if 'documentId' not in annotation_data:
                    doc_id_match = re.search(r'documentId:([^;]+)', content)
                    if doc_id_match:
                        annotation_data['documentId'] = doc_id_match.group(1)
                        content = re.sub(r'documentId:[^;]+;', '', content)
                annotation_data['content'] = content.strip()
                

                user_id_match = re.search(r'userId:([^;]+)', content)
                if user_id_match:
                    annotation_data['userId'] = user_id_match.group(1)
                    # Remove the userId part from the content to display clean content to user
                    content = re.sub(r'userId:[^;]+;', '', content)
                
                # Look for documentId in the content
                doc_id_match = re.search(r'documentId:([^;]+)', content)
                if doc_id_match:
                    annotation_data['documentId'] = doc_id_match.group(1)
                    # Remove the documentId part from the content to display clean content to user
                    content = re.sub(r'documentId:[^;]+;', '', content)
                
                # Update content with cleaned version (without IDs)
                annotation_data['content'] = content.strip()

                # Get annotation rectangle
                rect = annot.rect
                
                # Skip invalid rectangles (sometimes seen with text annotations)
                if rect.x0 < -1000000 or rect.y0 < -1000000:
                    print(f"Skipping annotation with invalid rectangle: {annotation_data['type']}")
                    continue
                
                annotation_data.update({
                    'x1': rect.x0,
                    'y1': rect.y0,
                    'x2': rect.x1,
                    'y2': rect.y1,
                    'width': rect.width,
                    'height': rect.height
                })
                subject = annot.info.get('subject', '')
                # In your extract_annotations function:
                if subject == 'textCallout':
                    annotation_data['type'] = 'textCallout'
                    rect = annot.rect
                    
                    # Get the title and extract metadata from it FIRST
                    title = annot.info.get('title', '')
                    
                    # Extract calloutId early to use for database lookup
                    callout_id_match = re.search(r'calloutId:([^;]+)', title)
                    if callout_id_match:
                        annotation_data['id'] = callout_id_match.group(1)
                        print(f"Found callout ID in title: {annotation_data['id']}")
                        
                        # Immediately try to get position from database using the found ID
                        try:
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            
                            db_query = """
                            SELECT text_left, text_top 
                            FROM text_callout_annotations 
                            WHERE id = ?
                            """
                            cursor.execute(db_query, [annotation_data['id']])
                            row = cursor.fetchone()

                            if row and row[0] is not None and row[1] is not None:
                                # Use exact database values
                                annotation_data['textLeft'] = float(row[0])  # This should be 352.161047813567
                                annotation_data['textTop'] = float(row[1])   # This should be 125.117486889766
                                print(f"Using database position - Left: {row[0]}, Top: {row[1]}")
                            else:
                                print("No database position found, using PDF coordinates")
                                annotation_data['textLeft'] = float(rect.x0)
                                annotation_data['textTop'] = float(rect.y0)
                            
                            conn.close()
                        except Exception as e:
                            print(f"Database error retrieving text position: {e}")
                            traceback.print_exc()
                            annotation_data['textLeft'] = float(rect.x0)
                            annotation_data['textTop'] = float(rect.y0)
                    else:
                        # No ID found, use PDF coordinates
                        annotation_data['textLeft'] = float(rect.x0)
                        annotation_data['textTop'] = float(rect.y0)
                    
                    # Set fixed dimensions
                    annotation_data['textWidth'] = 75
                    annotation_data['textHeight'] = 14.69

                    # Remove rectangle coordinates
                    annotation_data.pop('x1', None)
                    annotation_data.pop('y1', None)
                    annotation_data.pop('x2', None)
                    annotation_data.pop('y2', None)
                    annotation_data.pop('width', None)
                    annotation_data.pop('height', None)

                    # Rest of your existing code...
                    # Extract the actual text content (cleaned of metadata)
                    raw_content = annot.info.get('content', '')
                    cleaned_content = re.sub(r'(userId|documentId|calloutId):[^;]+;', '', raw_content).strip()
                    annotation_data['text'] = cleaned_content
                    
                    # Get the title and extract metadata from it
                    title = annot.info.get('title', '')
                    
                    # Extract calloutId, userId, documentId from title
                    callout_id_match = re.search(r'calloutId:([^;]+)', title)
                    if callout_id_match:
                        annotation_data['id'] = callout_id_match.group(1)
                        print(f"Found callout ID in title: {annotation_data['id']}")
                    
                    user_id_match = re.search(r'userId:([^;]+)', title)
                    if user_id_match:
                        annotation_data['userId'] = user_id_match.group(1)
                        print(f"Found user ID in title: {annotation_data['userId']}")
                    
                    doc_id_match = re.search(r'documentId:([^;]+)', title)
                    if doc_id_match:
                        annotation_data['documentId'] = doc_id_match.group(1)
                        print(f"Found document ID in title: {annotation_data['documentId']}")
                    
                    # Clean up the userName field if it contains metadata
                    user_name = annotation_data.get('userName', '')
                    if user_name and (user_name.startswith('userId:') or ';' in user_name):
                        # Try to extract a real username from elsewhere or set a default
                        annotation_data['userName'] = "Anurag Sable"  # Default fallback
                    
                    # IMPORTANT: Extract arrow coordinates from the PDF annotation
                    # PyMuPDF stores callout line information in the annotation
                    if hasattr(annot, 'callout'):
                        try:
                            callout_points = annot.callout
                            if callout_points and len(callout_points) >= 3:
                                # First point is typically the arrow start
                                annotation_data['arrowStart'] = [callout_points[0].x, callout_points[0].y]
                                # Second point is the arrow end / text connection point
                                annotation_data['arrowEnd'] = [callout_points[1].x, callout_points[1].y]
                                print(f"Extracted arrow points from PDF: start={annotation_data['arrowStart']}, end={annotation_data['arrowEnd']}")
                        except Exception as e:
                            print(f"Error extracting callout points: {e}")
                    
                    # If we have an ID, try to get data from database as backup
                    if 'id' in annotation_data:
                        try:
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            
                            # Query the database for this callout
                            db_query = "SELECT * FROM text_callout_annotations WHERE id = ?"
                            cursor.execute(db_query, [annotation_data['id']])
                            row = cursor.fetchone()
                            
                            if row:
                                # Found matching record in database
                                columns = [column[0] for column in cursor.description]
                                db_data = dict(zip(columns, row))
                                
                                print(f"Database record found: {db_data}")
                                
                                # Set arrowStart and arrowEnd from database if not already set
                                if ('arrowStart' not in annotation_data or not annotation_data['arrowStart']) and \
                                db_data.get('arrow_start_x') is not None and db_data.get('arrow_start_y') is not None:
                                    annotation_data['arrowStart'] = [db_data['arrow_start_x'], db_data['arrow_start_y']]
                                    print(f"Using arrow start from database: {annotation_data['arrowStart']}")
                                
                                if ('arrowEnd' not in annotation_data or not annotation_data['arrowEnd']) and \
                                db_data.get('arrow_end_x') is not None and db_data.get('arrow_end_y') is not None:
                                    annotation_data['arrowEnd'] = [db_data['arrow_end_x'], db_data['arrow_end_y']]
                                    print(f"Using arrow end from database: {annotation_data['arrowEnd']}")
                                
                                # Get other fields if needed
                                if db_data.get('user_name') and not annotation_data.get('userName', '').strip():
                                    annotation_data['userName'] = db_data['user_name']
                                
                                if db_data.get('text_content') and not annotation_data.get('text', '').strip():
                                    annotation_data['text'] = db_data['text_content']
                                
                                if db_data.get('font_size') and not annotation_data.get('fontSize'):
                                    annotation_data['fontSize'] = db_data['font_size']
                                
                                # Map other fields
                                field_mappings = {
                                    'arrow_color': 'arrowColor',
                                    'text_color': 'textColor',
                                    'border_color': 'borderColor'
                                }
                                
                                for db_field, annot_field in field_mappings.items():
                                    if db_field in db_data and db_data[db_field] and annot_field not in annotation_data:
                                        annotation_data[annot_field] = db_data[db_field]
                            else:
                                print(f"No database record found for callout ID: {annotation_data['id']}")
                            
                            conn.close()
                        except Exception as e:
                            print(f"Database error retrieving callout: {e}")
                            traceback.print_exc()
                    
                    # Ensure we have required fields with defaults if needed
                    if 'arrowStart' not in annotation_data or not annotation_data['arrowStart']:
                        # Default arrow start if not found (left of text box)
                        annotation_data['arrowStart'] = [rect.x0 - 50, rect.y0 + rect.height/2]
                        print(f"Using default arrowStart: {annotation_data['arrowStart']}")
                    
                    if 'arrowEnd' not in annotation_data or not annotation_data['arrowEnd']:
                        # Default arrow end (left edge of text box)
                        annotation_data['arrowEnd'] = [rect.x0, rect.y0 + rect.height/2]
                        print(f"Using default arrowEnd: {annotation_data['arrowEnd']}")
                    
                    if 'textColor' not in annotation_data:
                        annotation_data['textColor'] = 'red'
                    
                    if 'arrowColor' not in annotation_data:
                        annotation_data['arrowColor'] = 'red'
                    
                    if 'borderColor' not in annotation_data:
                        annotation_data['borderColor'] = 'red'

                
                        

                content = annot.info.get('content', '')


                # Handle specific annotation types
                if annotation_data['type'] == 'polyline':
                    # Get vertices for polyline
                    vertices = annot.vertices
                    if vertices:
                        # Convert tuple vertices to dict with x, y coordinates
                        annotation_data['points'] = [
                            {'x': vertex[0], 'y': vertex[1]} 
                            for vertex in vertices
                        ]
                        
                        # Also update the path for fabric.js
                        points = annotation_data['points']
                        if points:
                            path = f"M {points[0]['x']} {points[0]['y']}"
                            for point in points[1:]:
                                path += f" L {point['x']} {point['y']}"
                            annotation_data['path'] = path

                        # Determine if it's a cloud or freeDraw based on content or shape characteristics
                        content_lower = annotation_data['content'].lower()
                        subject_lower = annot.info.get('subject', '').lower()
                        
                        # Check for cloud annotation by content or subject
                        if "cloud" in content_lower or "cloud" in subject_lower:
                            annotation_data['type'] = 'cloud'
                            print(f"Identified cloud annotation from content: {annotation_data['id']}")
                        
                        # Check for freeDraw annotation based on content
                        elif any(term in content_lower for term in ["freedraw", "free draw"]) or any(term in subject_lower for term in ["freedraw", "free draw"]):
                            annotation_data['type'] = 'freeDraw'
                            print(f"Identified freeDraw annotation from content: {annotation_data['id']}")
                        
                        # If not identified by content, analyze shape characteristics
                        else:
                            # Calculate the area of the bounding box
                            area = rect.width * rect.height
                            
                            # Calculate the perimeter of the shape
                            perimeter = 0
                            for i in range(len(points)-1):
                                dx = points[i+1]['x'] - points[i]['x']
                                dy = points[i+1]['y'] - points[i]['y']
                                perimeter += (dx**2 + dy**2)**0.5
                            
                            # Check if the shape is closed
                            first_point = points[0]
                            last_point = points[-1]
                            dx = last_point['x'] - first_point['x']
                            dy = last_point['y'] - first_point['y']
                            is_closed = (dx**2 + dy**2)**0.5 < 20  # Threshold for "closedness"
                            
                            # Cloud detection - closed shape with reasonable perimeter-to-area ratio
                            if area > 0 and is_closed and perimeter / area < 0.5:
                                annotation_data['type'] = 'cloud'
                                print(f"Identified cloud annotation from shape analysis: {annotation_data['id']}")
                            # FreeDraw detection - many vertices or high perimeter-to-area ratio
                            elif len(vertices) > 30 or (area > 0 and perimeter / area > 1.0):
                                annotation_data['type'] = 'freeDraw'
                                print(f"Identified freeDraw annotation from analysis: {annotation_data['id']}")
                        
                        # For debugging
                        print(f"Annotation type: {annotation_data['type']}, Vertices: {len(vertices)}, Content: '{content_lower}'")
                
                elif annotation_data['type'] == 'text':
                    # Handle text annotations - ensure they have valid coordinates
                    # If coordinates are invalid, set reasonable defaults
                    if annotation_data['x1'] < 0 or annotation_data['y1'] < 0:
                        # Set default position in the center of the page
                        page_rect = page.rect
                        annotation_data.update({
                            'x1': page_rect.width / 2,
                            'y1': page_rect.height / 2,
                            'x2': page_rect.width / 2 + 100,  # Default width of 100
                            'y2': page_rect.height / 2 + 50,  # Default height of 50
                            'width': 100,
                            'height': 50
                        })
                    
                    # Skip text annotations with empty content
                    if not annotation_data['content'].strip():
                        print(f"Skipping text annotation with empty content: {annotation_data['id']}")
                        continue
                
                elif annotation_data['type'] in ['highlight', 'underline', 'strikeout']:
                    annotation_data['lineAnnotations'] = [{
                        'left': rect.x0,
                        'top': rect.y0,
                        'width': rect.width,
                        'height': rect.height
                    }]

                # Add stroke color and width if available
                if hasattr(annot, 'colors'):
                    stroke_color = annot.colors.get('stroke')
                    if stroke_color:
                        annotation_data['stroke'] = f'rgb({int(stroke_color[0]*255)}, {int(stroke_color[1]*255)}, {int(stroke_color[2]*255)})'
                
                if hasattr(annot, 'border'):
                    annotation_data['strokeWidth'] = annot.border.get('width', 1)

                # Add default stroke color if none is set
                if 'stroke' not in annotation_data:
                    annotation_data['stroke'] = 'rgb(255, 0, 0)'  # Default red color

                page_annotations.append(annotation_data)
            
            if page_annotations:
                annotations_by_page[str(page_num + 1)] = page_annotations

        # Create a clean PDF without annotations
        clean_doc = fitz.open(tmp_path)
        for page in clean_doc:
            for annot in page.annots():
                page.delete_annot(annot)

        # Save clean PDF to memory
        clean_pdf_bytes = clean_doc.write()
        clean_pdf_base64 = base64.b64encode(clean_pdf_bytes).decode('utf-8')

        # Clean up
        doc.close()
        clean_doc.close()
        os.unlink(tmp_path)

        print("Extracted annotations:", annotations_by_page)  

        return jsonify({
            'annotations': annotations_by_page,
            'cleanPdfContent': clean_pdf_base64,
            'message': 'Annotations extracted successfully'
        })

    except Exception as e:
        print(f"Error extracting annotations: {str(e)}")  
        import traceback
        traceback.print_exc()  
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/merge-annotated-pdf', methods=['POST'])
def merge_annotated_pdf():
    try:
        try:
            conn = None
            conn = get_db_connection()
            if not conn:
                    raise Exception("Failed to establish database connection")
                    
            cursor = conn.cursor()

            print("Received download request")
            
            if 'file' not in request.files:
                print("No file in request")
                return jsonify({"error": "No file part"}), 400
                
            file = request.files['file']
            annotations_json = request.form.get('annotations')
            document_id = request.form.get('DocumentId')
            user_id = request.form.get('userId')
            return_binary = request.form.get('returnBinary', 'false').lower() == 'true'


            if not document_id or not user_id:
                return jsonify({"error": "Missing DocumentId or userId"}), 400

            if not annotations_json:
                print("No annotations provided")
                return jsonify({"error": "No annotations provided"}), 400

            # Read the PDF file
            pdf_bytes = file.read()
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            annotations = json.loads(annotations_json)
            print(f"Processing {len(annotations)} annotations")

            # Process annotations (reuse your existing annotation processing code)
            for annotation in annotations:
                try:
                    page_num = int(annotation.get("page", 1))
                    if page_num <= 0:
                        page_num = 1
                    page = pdf_document[page_num - 1]  # Convert to 0-based index

                    if "documentId" not in annotation:
                        annotation["documentId"] = document_id
                    if "userId" not in annotation:
                        annotation["userId"] = user_id

                    
                    
                    print(f"Processing annotation type: {annotation['type']} on page {page_num}")

                    id_metadata = f"userId:{annotation['userId']};documentId:{annotation['documentId']};"

                    if "type" in annotation and annotation["type"] == "text" or all(key in annotation for key in ["x1", "y1", "x2", "y2", "text"]):
                        try:
                            print(f"Processing text annotation: {annotation}")
                            
                            # Create the rectangle for the text annotation
                            rect = fitz.Rect(
                                annotation["x1"], 
                                annotation["y1"], 
                                annotation["x2"], 
                                annotation["y2"]
                            )

                            annotation_text = annotation.get("content") 
                            
                            # Add the text annotation with proper parameters
                            text_annotation = page.add_freetext_annot(
                                rect=rect,
                                text=annotation_text,
                                fontsize=float(annotation.get("fontSize", 11)),
                                fontname="Helv",
                                text_color=(0, 0, 0),  # Black text
                                # fill_color=(1, 1, 1),  # White background
                                border_color=(0, 0, 0)  # Black border
                            )
                            
                            # Set metadata
                            text_annotation.set_info(
                                title=id_metadata,
                                subject=annotation.get("subject", "Text"),
                                content= annotation.get("content", annotation["text"])
                            )
                            
                            # Set border and make printable
                            text_annotation.set_border(width=0.5)
                            text_annotation.set_flags(fitz.PDF_ANNOT_IS_PRINT)
                            
                            # Update appearance
                            text_annotation.update()
                            # page.set_dirty()
                            
                            print("✅ Text annotation added successfully")
                            
                        except Exception as e:
                            print(f"Error processing text annotation: {e}")
                            traceback.print_exc()
                    
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
                                content=id_metadata + annotation.get("content", "")
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
                                content=id_metadata + annotation.get("content", "This text is highlighted.")
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
                                content=id_metadata + annotation.get("content", "This text is highlighted.")
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
                                            content=id_metadata + annotation.get("content", "This text is highlighted.")
                                        )
                                        highlight_annot.update()
                                        print(annotation)
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
                                content=id_metadata + annotation.get("content", "This text is underlined.")
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
                                content=id_metadata + annotation.get("content", "This text is underlined.")
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
                                                content=id_metadata + annotation.get("content", "This text is underlined.")
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
                                content=id_metadata + annotation.get("content", "This text has been struck out.")
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
                                content=id_metadata + annotation.get("content", "This text has been struck out.")
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
                                                content=id_metadata + annotation.get("content", "This text is struck out.")
                                            )
                                            strikeout_annot.update()
                                            print(annotation)
                                    else:
                                        print(f"Missing coordinates for line annotation: {line}")
                        else:
                            print(f"Missing coordinates for strike-out annotation: {annotation}")
                        
                    # elif annotation["type"] == "stamp":
                    #     img_src = annotation.get("imgSrc")
                    #     x1 = annotation.get("x1")
                    #     y1 = annotation.get("y1")
                    #     x2 = annotation.get("x2")
                    #     y2 = annotation.get("y2")

                    #     if img_src and x1 is not None and y1 is not None and x2 is not None and y2 is not None:
                    #         width = x2 - x1
                    #         height = y2 - y1

                    #         img_path = os.path.join(os.getcwd(), img_src.lstrip('/'))
                    #         if os.path.exists(img_path):
                    #             try:
                    #                 # Create the stamp rectangle with exact coordinates
                    #                 stamp_rect = fitz.Rect(x1, y1, x2, y2)
                                    
                    #                 # Create a stamp annotation
                    #                 stamp_annot = page.add_stamp_annot(stamp_rect)
                                    
                    #                 # Read and process the image
                    #                 with open(img_path, "rb") as img_file:
                    #                     img_data = img_file.read()
                                    
                    #                 # Set the appearance stream directly with the image data
                    #                 stamp_annot.set_appearance(stream=img_data, content=img_data)
                                    
                    #                 # Set PDF dictionary properties
                    #                 pdf_dict = stamp_annot.get_pdf_obj()
                    #                 pdf_dict.update({
                    #                     'Subtype': '/Stamp',
                    #                     'Name': '/StampAnnotation',
                    #                     'F': 4,  # Annotation flags
                    #                     'Rect': [stamp_rect.x0, stamp_rect.y0, stamp_rect.x1, stamp_rect.y1]
                    #                 })
                                    
                    #                 # Set metadata
                    #                 stamp_annot.set_info(
                    #                     title=annotation.get("userName", "Anurag Sable"),
                    #                     subject="Stamp",
                    #                     content=annotation.get("content", "This is a stamp annotation")
                    #                 )
                                    
                    #                 # Update the annotation
                    #                 stamp_annot.update()
                                    
                    #                 print(f"Stamp annotation added successfully at: {stamp_rect}")
                                    
                    #             except Exception as e:
                    #                 print(f"Error processing stamp annotation: {e}")
                    #                 print(f"Error details: {str(e)}")
                    #         else:
                    #             print(f"Image file not found: {img_path}")
                    #     else:
                    #         print("Missing required stamp annotation properties")

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
                                content=id_metadata + annotation.get("content", "This is a stamp annotation")
                            )
                            stamp_annot.update()

                    # elif annotation["type"] == "signature":
                    #     img_data = annotation.get("dataURL")
                    #     x1, y1 = annotation.get("x1"), annotation.get("y1")
                    #     x2, y2 = annotation.get("x2"), annotation.get("y2")

                    #     if img_data and None not in (x1, y1, x2, y2):
                    #         try:
                    #             # Decode base64 image data
                    #             if "," in img_data:
                    #                 img_bytes = base64.b64decode(img_data.split(",")[1])
                    #             else:
                    #                 img_bytes = base64.b64decode(img_data)

                    #             # Create a signature annotation
                    #             sig_rect = fitz.Rect(x1-400, y1-80, x2, y2-80)
                    #             sig_annot = page.add_stamp_annot(sig_rect)  # Use stamp annotation for signatures
                                
                    #             # Set the signature image as the appearance
                    #             sig_annot.set_appearance(stream=img_bytes, content=img_bytes)
                                
                    #             # Set metadata
                    #             sig_annot.set_info(
                    #                 title=annotation.get("userName", "Anurag Sable"),
                    #                 subject="Signature",
                    #                 content=annotation.get("content", "This is a signature annotation")
                    #             )
                    #             sig_annot.update()
                    #             print(f"Signature annotation successfully added at page {annotation.get('page')}")

                    #         except Exception as e:
                    #             print(f"Error adding signature annotation: {e}")

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
                                content=id_metadata + annotation.get("content", "This is a signature annotation")
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
                                content=id_metadata + annotation.get("content", "")
                            )
                            square_annot.set_colors(stroke=[1, 0, 0])  # Red in RGB format
                            square_annot.set_border(width=annotation.get("strokeWidth", 1))
                            square_annot.update()
                            print(f"Added square annotation: {annotation}")
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
                                    content=id_metadata + annotation.get("content", "")
                                )
                                circle_annot.set_border(width=2)  # Set stroke width to 2

                                circle_annot.update()
                            else:
                                print(f"Invalid radius for circle annotation: {annotation}")
                        else:
                            print(f"Missing data for circle annotation: {annotation}")

                    elif annotation["type"] == "cloud":
                        try:
                            print("Processing cloud annotation... Block 1")
                            if "path" in annotation and isinstance(annotation["path"], list):
                                try:
                                    print("Processing cloud annotation... Block 1.1")
                                    cloud_path = annotation['path']
                                    points = []
                                    vertices = []
                                    
                                    # Convert path commands to points with better curve handling
                                    current_point = None
                                    for command in cloud_path:
                                        try:
                                            if command[0] == 'M':  # Move to
                                                current_point = fitz.Point(command[1], command[2])
                                                points.append(current_point)
                                                vertices.append(current_point)
                                            elif command[0] == 'L':  # Line to
                                                current_point = fitz.Point(command[1], command[2])
                                                points.append(current_point)
                                                vertices.append(current_point)
                                            elif command[0] == 'C':  # Cubic bezier curve
                                                start = current_point
                                                c1 = fitz.Point(command[1], command[2])
                                                c2 = fitz.Point(command[3], command[4])
                                                end = fitz.Point(command[5], command[6])
                                                
                                                steps = 10
                                                for i in range(1, steps + 1):
                                                    t = i / steps
                                                    x = (1-t)**3 * start.x + 3*(1-t)**2 * t * c1.x + 3*(1-t) * t**2 * c2.x + t**3 * end.x
                                                    y = (1-t)**3 * start.y + 3*(1-t)**2 * t * c1.y + 3*(1-t) * t**2 * c2.y + t**3 * end.y
                                                    point = fitz.Point(x, y)
                                                    points.append(point)
                                                    vertices.append(point)
                                                current_point = end
                                        except Exception as e:
                                            print(f"Error processing command: {e}")
                                            continue

                                    print(f"Total points generated: {len(points)}")
                                    if points:
                                        try:
                                            cloud_annot = page.add_polyline_annot(points)
                                            cloud_annot.set_border(width=annotation.get("strokeWidth", 2))
                                            cloud_annot.set_colors(stroke=(1, 0, 0))  # Red color
                                            cloud_annot.set_info(
                                                title=annotation.get("userName", "Anurag Sable"),
                                                subject="Cloud",
                                                content=id_metadata + annotation.get("content", "")
                                            )

                                            if points[0] != points[-1]:
                                                points.append(points[0])
                                                vertices.append(vertices[0])

                                            cloud_annot.update()
                                            print(annotation)
                                            print(f"Cloud annotation added successfully")
                                        except Exception as e:
                                            print(f"Error creating cloud annotation: {e}")
                                    else:
                                        print("No valid points generated for cloud annotation")
                                except Exception as e:
                                    print(f"Error processing cloud path: {e}")
                                    raise  # Re-raise to trigger fallback
                            else:
                                raise ValueError("Invalid path format")  # Trigger fallback method

                        except Exception as e:
                            print(f"Error in first block cloud 1: {e}. Trying fallback method.")

                            try:
                                print("Using fallback method... Block 2")
                                if "path" in annotation:
                                    try:
                                        path = annotation["path"].split(' ')
                                        points = []
                                        vertices = []

                                        # Parse the path string into points
                                        for i in range(0, len(path), 3):
                                            try:
                                                command = path[i]
                                                if command == 'M' or command == 'L':
                                                    x = float(path[i + 1])
                                                    y = float(path[i + 2])
                                                    point = fitz.Point(x, y)
                                                    points.append(point)
                                                    vertices.append(point)
                                            except Exception as e:
                                                print(f"Error processing fallback command: {e}")
                                                continue

                                        print(f"Fallback: Total points generated: {len(points)}")
                                        if points:
                                            try:
                                                cloud_annot = page.add_polyline_annot(points)
                                                cloud_annot.set_border(width=annotation.get("strokeWidth", 2))
                                                cloud_annot.set_colors(stroke=(1, 0, 0))  # Red color
                                                cloud_annot.set_info(
                                                    title=annotation.get("userName", "Anurag Sable"),
                                                    subject="Cloud",
                                                    content=id_metadata + annotation.get("content", "")
                                                )

                                                if points[0] != points[-1]:
                                                    points.append(points[0])
                                                    vertices.append(vertices[0])

                                                cloud_annot.update()
                                                print(f"Cloud annotation added successfully (fallback method)")
                                            except Exception as e:
                                                print(f"Error creating cloud annotation in fallback: {e}")
                                        else:
                                            print("No valid points generated in fallback method")
                                    except Exception as e:
                                        print(f"Error processing fallback path: {e}")
                                else:
                                    print("No path data available for fallback method")
                            except Exception as e:
                                print(f"Error in fallback block cloud: {e}")
                    # elif annotation["type"] == "cloud":
                    #     if "path" in annotation and isinstance(annotation["path"], list):
                    #         cloud_path = annotation['path']
                    #         points = []
                    #         for command in cloud_path:
                    #             if command[0] == 'M':
                    #                 points.append(fitz.Point(command[1], command[2]))
                    #             elif command[0] == 'L':
                    #                 points.append(fitz.Point(command[1], command[2]))
                    #             elif command[0] == 'C':
                    #                 points.append(fitz.Point(command[1], command[2]))
                    #                 points.append(fitz.Point(command[3], command[4]))
                    #                 points.append(fitz.Point(command[5], command[6]))
                    #         try:
                    #             cloud_annot = page.add_polyline_annot(points)
                    #             cloud_annot.set_info(
                    #                 title=annotation.get("userName", "Anurag Sable"),
                    #                 subject=annotation.get("subject", "Cloud"),
                    #                 content=annotation.get("content", "")
                    #            )
                    #             page.draw_polyline(
                    #                 points,
                    #                 color=(1, 0, 0),
                    #                 width=annotation.get("strokeWidth", 2),
                    #                 closePath=True
                    #             )
                    #         except Exception as e:
                    #             print(f"Error drawing cloud annotation: {e}")
                    #     else:
                    #         print(f"Missing path data for cloud annotation: {annotation}")

                    elif annotation["type"] == "freeDraw":
                        try:
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
                                    content=id_metadata + annotation.get("content", "")
                                )

                                # Set appearance properties
                                free_draw_annot.set_colors(stroke=(1, 0, 0))  # Red color
                                free_draw_annot.set_border(width=annotation.get("strokeWidth", 2))

                                # Finalize the annotation
                                free_draw_annot.update()
                                print(f"FreeDraw annotation added successfully {annotation}")
                        except Exception as e:
                            print(f"Error in first block: {e}. Trying fallback method.")
                            
                            try:
                                if "path" in annotation:
                                    path = annotation["path"]
                                    fitz_path = []

                                    # Convert path string to a list of commands
                                    if isinstance(path, str):
                                        path = path.split(' ')

                                    # Ensure path is a list of commands
                                    for i in range(0, len(path), 3):
                                        try:
                                            command = path[i:i+3]
                                            if command[0] == 'M' and len(command) >= 3:  # Move to
                                                fitz_path.append(fitz.Point(float(command[1]), float(command[2])))
                                            elif command[0] == 'L' and len(command) >= 3:  # Line to
                                                fitz_path.append(fitz.Point(float(command[1]), float(command[2])))
                                            elif command[0] == 'Q' and len(command) >= 5:  # Quadratic curve
                                                fitz_path.append(fitz.Point(float(command[1]), float(command[2])))
                                                fitz_path.append(fitz.Point(float(command[3]), float(command[4])))
                                            else:
                                                print(f"Unexpected command format: {command}")
                                        except (IndexError, ValueError) as e:
                                            print(f"Error processing command {command}: {e}")

                                    if fitz_path:
                                        # Create a polyline annotation for FreeDraw
                                        free_draw_annot = page.add_polyline_annot(fitz_path)

                                        # Set metadata for the annotation
                                        free_draw_annot.set_info(
                                            title=annotation.get("userName", "Anurag Sable"),
                                            subject=annotation.get("subject", ""),
                                            content=id_metadata + annotation.get("content", "")
                                        )

                                        # Set appearance properties
                                        free_draw_annot.set_colors(stroke=(1, 0, 0))  # Red color
                                        free_draw_annot.set_border(width=annotation.get("strokeWidth", 2))

                                        # Finalize the annotation
                                        free_draw_annot.update()
                                        print(f"FreeDraw annotation added successfully {annotation}")   
                                    else:
                                        print(f"No valid points found for freeDraw annotation: {annotation}")
                                else:
                                    print(f"Missing path data for freeDraw annotation: {annotation}")
                            except Exception as e:
                                print(f"Error in fallback block: {e}")

                    elif annotation["type"] == "textCallout":
                        try:
                            if not annotation.get('id'):
                                annotation['id'] = f"callout_{uuid.uuid4().hex[:8]}"
                        
                            callout_id = annotation.get('id')
                            sql = """
                            IF EXISTS (SELECT 1 FROM text_callout_annotations WHERE id = ?)
                            BEGIN
                                UPDATE text_callout_annotations
                                SET document_id = ?,
                                    user_id = ?,
                                    user_name = ?,
                                    page_number = ?,
                                    text_content = ?,
                                    arrow_start_x = ?,
                                    arrow_start_y = ?,
                                    arrow_end_x = ?,
                                    arrow_end_y = ?,
                                    text_left = ?,
                                    text_top = ?,
                                    text_width = ?,
                                    text_height = ?,
                                    font_size = ?,
                                    arrow_color = ?,
                                    text_color = ?,
                                    border_color = ?
                                WHERE id = ?
                            END
                            ELSE
                            BEGIN
                                INSERT INTO text_callout_annotations (
                                    id, document_id, user_id, user_name, page_number,
                                    text_content, arrow_start_x, arrow_start_y,
                                    arrow_end_x, arrow_end_y, text_left, text_top,
                                    text_width, text_height, font_size,
                                    arrow_color, text_color, border_color
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            END
                            """

                            values = [
                                callout_id,  # For the IF EXISTS check
                                # UPDATE values
                                document_id,
                                user_id,
                                annotation.get('userName'),
                                annotation.get('page'),
                                annotation.get('text'),
                                annotation['arrowStart'][0] if 'arrowStart' in annotation else None,
                                annotation['arrowStart'][1] if 'arrowStart' in annotation else None,
                                annotation['arrowEnd'][0] if 'arrowEnd' in annotation else None,
                                annotation['arrowEnd'][1] if 'arrowEnd' in annotation else None,
                                annotation.get('textLeft'),
                                annotation.get('textTop'),
                                annotation.get('textWidth'),
                                annotation.get('textHeight'),
                                annotation.get('fontSize'),
                                annotation.get('arrowColor'),
                                annotation.get('textColor'),
                                annotation.get('borderColor'),
                                callout_id,
                                callout_id,
                                document_id,
                                user_id,
                                annotation.get('userName'),
                                annotation.get('page'),
                                annotation.get('text'),
                                annotation['arrowStart'][0] if 'arrowStart' in annotation else None,
                                annotation['arrowStart'][1] if 'arrowStart' in annotation else None,
                                annotation['arrowEnd'][0] if 'arrowEnd' in annotation else None,
                                annotation['arrowEnd'][1] if 'arrowEnd' in annotation else None,
                                annotation.get('textLeft'),
                                annotation.get('textTop'),
                                annotation.get('textWidth'),
                                annotation.get('textHeight'),
                                annotation.get('fontSize'),
                                annotation.get('arrowColor'),
                                annotation.get('textColor'),
                                annotation.get('borderColor')
                            ]
                            
                            cursor.execute(sql, values)
                            conn.commit()
                            print(f"Saved text callout annotation: {annotation.get('id')}")
                            print(f"Processing text callout annotation: {annotation}")

                            try:
                                check_query = "SELECT COUNT(*) FROM text_callout_annotations WHERE id = ?"
                                cursor.execute(check_query, [annotation.get('id')])
                                count = cursor.fetchone()[0]
                                print(f"Verification: Found {count} records with ID {annotation.get('id')}")
                            except Exception as e:
                                print(f"Error verifying saved record: {e}")


                            required_keys = ["arrowStart", "arrowEnd", "textLeft", "textTop"]
                            if not all(key in annotation for key in required_keys):
                                print("Missing required fields for textCallout annotation")
                                continue

                            annotation_metadata = f"calloutId:{callout_id};userId:{user_id};documentId:{document_id};"

                            # Extract coordinates
                            arrow_start_x, arrow_start_y = annotation["arrowStart"]
                            arrow_end_x, arrow_end_y = annotation["arrowEnd"]
                            text_left = annotation["textLeft"]
                            text_top = annotation["textTop"]
                            text_content = annotation.get("text", "")
                            
                            # Calculate text dimensions to ensure full text visibility
                            font_size = float(annotation.get("fontSize", 11) or 11)
                            # Use a temporary annotation to calculate text dimensions
                            temp_rect = fitz.Rect(0, 0, 100, 100)  # temporary rectangle
                            temp_annot = page.add_freetext_annot(
                                rect=temp_rect,
                                text=text_content,
                                fontsize=font_size,
                                fontname="Helv"
                            )
                            text_bounds = temp_annot.rect
                            page.delete_annot(temp_annot)
                            
                            # Add padding to ensure text isn't clipped
                            text_width = float(annotation["textWidth"])
                            text_height = float(annotation["textHeight"])

                            # Create the text rectangle with calculated dimensions
                            text_rect = fitz.Rect(
                                text_left, 
                                text_top, 
                                text_left + text_width,
                                text_top + text_height
                            )
                            
                            arrow_color = validate_and_normalize_color(annotation.get("arrowColor", (1, 0, 0)))
                            text_color = validate_and_normalize_color(annotation.get("textColor", (1, 0, 0)))
                            border_color = validate_and_normalize_color(annotation.get("borderColor", (1, 0, 0)))
                            
                            user_name = annotation.get("userName", "Anonymous")

                            # Define callout points
                            p1 = fitz.Point(arrow_start_x, arrow_start_y)
                            p2 = fitz.Point(arrow_end_x, arrow_end_y)
                            p3 = fitz.Point(text_left, text_top + text_height/2)

                            # Create the callout annotation with adjusted properties
                            callout_annot = page.add_freetext_annot(
                                rect=text_rect,
                                text=text_content,
                                fontsize=font_size,
                                fontname="Helv",
                                text_color=text_color,
                                fill_color=(1, 1, 1),  # White background
                                border_color=border_color,
                                callout=(p1, p2, p3),
                                line_end=fitz.PDF_ANNOT_LE_CLOSED_ARROW,
                                border_width=annotation.get("arrowWidth", 1),
                                align=0  # Left alignment
                            )

                            # Set additional properties to ensure visibility
                            callout_annot.set_flags(
                                fitz.PDF_ANNOT_IS_PRINT |  # Make it printable
                                fitz.PDF_ANNOT_IS_NO_ZOOM |  # Don't scale with zoom
                                fitz.PDF_ANNOT_IS_NO_ROTATE  # Don't rotate
                            )
                            
                            # Set metadata
                            callout_annot.set_info(
                                title=annotation_metadata,
                                subject="textCallout",
                                content= text_content
                            )

                            # callout_annot.set_text(text_content)

                            # Force update appearance
                            callout_annot.update()  # Force appearance update
                            
                            print("✅ Unified Text Callout annotation added successfully")
                            
                        except Exception as e:
                            print(f"Error adding text callout annotation: {e}")
                            traceback.print_exc()

        
                        
                except Exception as e:
                    print(f"Error processing annotation: {e}")  
                    continue

        except Exception as e:
            print(f"Database operation error: {e}")
            if conn:
                conn.rollback()
            raise

        finally:
            if conn:
                try:
                    conn.close()
                except Exception as e:
                    print(f"Error closing connection: {e}")    


        #     for page_num in processed_pages:
        #         page = pdf_document.load_page(page_num)
        #         page.apply_transform_matrix(fitz.Matrix(1, 0, 0, 1, 0, 0))

        # # Force commit all changes before final save
        #     pdf_document.save_incremental()

        # Save to memory buffer
        output_buffer = io.BytesIO()
        pdf_document.save(output_buffer)
        pdf_document.close()
        output_buffer.seek(0)

        if return_binary:
                filename = f"annotated_{document_id}.pdf"
                return Response(
                    output_buffer.getvalue(),
                    status=200,
                    mimetype='application/pdf',
                    headers={
                        'Content-Disposition': f'attachment; filename={filename}',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Methods': 'POST, OPTIONS',
                        'Access-Control-Allow-Headers': 'Content-Type'
                    }
                )
        
        files = {
            'file': ('annotated.pdf', output_buffer, 'application/pdf')
        }
        data = {
            'DocumentId': "E0C9216C-1C1F-4412-9786-047A4E6771F8"
            # 'DocumentId': document_id
        }
        
        print("Sending request to external API")
        response = requests.post(
            'http://idmsdemo.vishwatechnologies.com/api/comment/mergepdf',
            files=files,
            data=data,
            verify=False
        )
        
        print(f"External API response status: {response.status_code}")
        print(f"External API response: {response.text}")
        
        
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


@app.route('/api/get-pdf', methods=['GET'])
def get_pdf():
    try:
        
        # pdf_id = request.args.get('pdfId')
        
        # if not pdf_id:
        #     return jsonify({'error': 'PDF ID must be provided'}), 400
        
        
        pdf_url = f"http://idmsdemo.vishwatechnologies.com/Temp/merged_document.pdf"
        
        
        response = requests.get(pdf_url, verify=False)
        response.raise_for_status()
        
        
        return response.content, 200, {
            'Content-Type': 'application/pdf',
            'Content-Disposition': f'attachment; filename={pdf_id}.pdf'
        }
    
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Failed to retrieve PDF: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500   
        


@app.route('/api/receive-pdf-links', methods=['POST'])
def receive_pdf_links():
    try:
        data = request.json
        pdf_urls = data.get('pdfUrls', [])
        
        if not pdf_urls:
            return jsonify({'error': 'No PDF URLs provided'}), 400
        
        # Store the PDF URLs in the app config for later use
        app.config['PDF_URLS'] = pdf_urls
        
        # Store default PDF IDs if needed
        if 'CURRENT_PDF_IDS' not in app.config or not app.config['CURRENT_PDF_IDS']:
            app.config['CURRENT_PDF_IDS'] = [f'pdf_{i}' for i in range(len(pdf_urls))]
        
        return jsonify({
            'status': 'success',
            'message': f'Received {len(pdf_urls)} PDF URLs',
            'urls': pdf_urls
        })
    except Exception as e:
        print(f"Error receiving PDF links: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


def extract_annotations_from_local_files():
    try:
        pdf_urls = app.config.get('PDF_URLS', [])
        
        if not pdf_urls:
            print("No PDF URLs found in app config, using defaults")
            pdf_urls = [
            ]
        
        print(f"Using PDF URLs from frontend: {pdf_urls}")
        
        pdf_ids = app.config.get('CURRENT_PDF_IDS', [f'pdf_{i}' for i in range(len(pdf_urls))])
        combined_annotations_by_page = {}
        clean_pdf_base64 = None
        processed_ids = []

        for i, pdf_url in enumerate(pdf_urls):
            pdf_id = pdf_ids[i] if i < len(pdf_ids) else f"pdf_{i}"
            
            # Open the PDF with PyMuPDF
            print(f"Downloading PDF from: {pdf_url}")
            response = requests.get(pdf_url, verify=False)
            response.raise_for_status() 
                    
            pdf_stream = io.BytesIO(response.content)
                    
            doc = fitz.open(stream=pdf_stream, filetype="pdf")
                    
            print(f"Successfully opened PDF with ID {pdf_id}")
            processed_ids.append(pdf_id)
            
            # Extract annotations from each page
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_annotations = []
                    
                for annot in page.annots():
                    annotation_type = annot.type[1].lower()  
                    if annotation_type == 'freetext':
                        annotation_type = 'text'
                    annotation_data = {
                        'id': str(uuid.uuid4()),
                        'type': annotation_type,  
                        'page': page_num + 1,
                        'content': annot.info.get('content', ''),
                        'userName': annot.info.get('title', 'Unknown'),
                        'createdAt': datetime.now().isoformat()
                    }
                    title = annot.info.get('title', '')
                    content = annot.info.get('content', '')

                    if annotation_type == 'text':
                        # Try to extract userId from title first
                        user_id_match = re.search(r'userId:([^;]+)', title)
                        if user_id_match:
                            annotation_data['userId'] = user_id_match.group(1)
                            print(f"Found user ID in title for text annotation: {annotation_data['userId']}")
                            
                        # Try to extract documentId from title
                        doc_id_match = re.search(r'documentId:([^;]+)', title)
                        if doc_id_match:
                            annotation_data['documentId'] = doc_id_match.group(1)
                            print(f"Found document ID in title for text annotation: {annotation_data['documentId']}")
                    # If not found in title or not a text annotation, check content
                    if 'userId' not in annotation_data:
                        user_id_match = re.search(r'userId:([^;]+)', content)
                        if user_id_match:
                            annotation_data['userId'] = user_id_match.group(1)
                            content = re.sub(r'userId:[^;]+;', '', content)
                    
                    if 'documentId' not in annotation_data:
                        doc_id_match = re.search(r'documentId:([^;]+)', content)
                        if doc_id_match:
                            annotation_data['documentId'] = doc_id_match.group(1)
                            content = re.sub(r'documentId:[^;]+;', '', content)
                    annotation_data['content'] = content.strip()
                    
                    user_id_match = re.search(r'userId:([^;]+)', content)
                    if user_id_match:
                        annotation_data['userId'] = user_id_match.group(1)
                        # Remove the userId part from the content to display clean content to user
                        content = re.sub(r'userId:[^;]+;', '', content)
                    
                    # Look for documentId in the content
                    doc_id_match = re.search(r'documentId:([^;]+)', content)
                    if doc_id_match:
                        annotation_data['documentId'] = doc_id_match.group(1)
                        # Remove the documentId part from the content to display clean content to user
                        content = re.sub(r'documentId:[^;]+;', '', content)
                    
                    # Update content with cleaned version (without IDs)
                    annotation_data['content'] = content.strip()
                    # Get annotation rectangle
                    rect = annot.rect
                    
                    # Skip invalid rectangles (sometimes seen with text annotations)
                    if rect.x0 < -1000000 or rect.y0 < -1000000:
                        print(f"Skipping annotation with invalid rectangle: {annotation_data['type']}")
                        continue
                    
                    annotation_data.update({
                        'x1': rect.x0,
                        'y1': rect.y0,
                        'x2': rect.x1,
                        'y2': rect.y1,
                        'width': rect.width,
                        'height': rect.height
                    })
                    
                    # ADD THIS NEW CODE HERE - Check for highlight, underline, strikeout - BEFORE other conditionals
                    if annotation_data['type'] in ['highlight', 'underline', 'strikeout']:
                        annotation_data['lineAnnotations'] = [{
                            'left': rect.x0,
                            'top': rect.y0,
                            'width': rect.width,
                            'height': rect.height
                        }]
                        print(f"Added lineAnnotations for {annotation_data['type']}: {annotation_data['lineAnnotations']}")
                    
                    subject = annot.info.get('subject', '')
                    # In your extract_annotations function:
                    if subject == 'textCallout':
                        annotation_data['type'] = 'textCallout'
                        rect = annot.rect
                        
                        # Get the title and extract metadata from it FIRST
                        title = annot.info.get('title', '')
                        
                        # Extract calloutId early to use for database lookup
                        callout_id_match = re.search(r'calloutId:([^;]+)', title)
                        if callout_id_match:
                            annotation_data['id'] = callout_id_match.group(1)
                            print(f"Found callout ID in title: {annotation_data['id']}")
                            
                            # Immediately try to get position from database using the found ID
                            try:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                
                                db_query = """
                                SELECT text_left, text_top 
                                FROM text_callout_annotations 
                                WHERE id = ?
                                """
                                cursor.execute(db_query, [annotation_data['id']])
                                row = cursor.fetchone()

                                if row and row[0] is not None and row[1] is not None:
                                    # Use exact database values
                                    annotation_data['textLeft'] = float(row[0])
                                    annotation_data['textTop'] = float(row[1])
                                    print(f"Using database position - Left: {row[0]}, Top: {row[1]}")
                                else:
                                    print("No database position found, using PDF coordinates")
                                    annotation_data['textLeft'] = float(rect.x0)
                                    annotation_data['textTop'] = float(rect.y0)
                                
                                conn.close()
                            except Exception as e:
                                print(f"Database error retrieving text position: {e}")
                                traceback.print_exc()
                                annotation_data['textLeft'] = float(rect.x0)
                                annotation_data['textTop'] = float(rect.y0)
                        else:
                            # No ID found, use PDF coordinates
                            annotation_data['textLeft'] = float(rect.x0)
                            annotation_data['textTop'] = float(rect.y0)
                        
                        # Set fixed dimensions
                        annotation_data['textWidth'] = 75
                        annotation_data['textHeight'] = 14.69
                        # Remove rectangle coordinates
                        annotation_data.pop('x1', None)
                        annotation_data.pop('y1', None)
                        annotation_data.pop('x2', None)
                        annotation_data.pop('y2', None)
                        annotation_data.pop('width', None)
                        annotation_data.pop('height', None)

                        # Rest of your existing code...
                        # Extract the actual text content (cleaned of metadata)
                        raw_content = annot.info.get('content', '')
                        cleaned_content = re.sub(r'(userId|documentId|calloutId):[^;]+;', '', raw_content).strip()
                        annotation_data['text'] = cleaned_content
                            
                        # Get the title and extract metadata from it
                        title = annot.info.get('title', '')
                            
                        # Extract calloutId, userId, documentId from title
                        callout_id_match = re.search(r'calloutId:([^;]+)', title)
                        if callout_id_match:
                            print(f"Found callout ID in title: {annotation_data['id']}")
                        
                        user_id_match = re.search(r'userId:([^;]+)', title)
                        if user_id_match:
                            annotation_data['userId'] = user_id_match.group(1)
                            print(f"Found user ID in title: {annotation_data['userId']}")
                            
                        doc_id_match = re.search(r'documentId:([^;]+)', title)
                        if doc_id_match:
                            annotation_data['documentId'] = doc_id_match.group(1)
                            print(f"Found document ID in title: {annotation_data['documentId']}")
                            
                        # Clean up the userName field if it contains metadata
                        user_name = annotation_data.get('userName', '')
                        if user_name and (user_name.startswith('userId:') or ';' in user_name):
                            # Try to extract a real username from elsewhere or set a default
                            annotation_data['userName'] = "Anurag Sable"  # Default fallback
                            
                        # IMPORTANT: Extract arrow coordinates from the PDF annotation
                        # PyMuPDF stores callout line information in the annotation
                        if hasattr(annot, 'callout'):
                            try:
                                callout_points = annot.callout
                                if callout_points and len(callout_points) >= 3:
                                    # First point is typically the arrow start
                                    annotation_data['arrowStart'] = [callout_points[0].x, callout_points[0].y]
                                    # Second point is the arrow end / text connection point
                                    annotation_data['arrowEnd'] = [callout_points[1].x, callout_points[1].y]
                                    print(f"Extracted arrow points from PDF: start={annotation_data['arrowStart']}, end={annotation_data['arrowEnd']}")
                            except Exception as e:
                                print(f"Error extracting callout points: {e}")
                            
                        # If we have an ID, try to get data from database as backup
                        if 'id' in annotation_data:
                            try:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                    
                                # Query the database for this callout
                                db_query = "SELECT * FROM text_callout_annotations WHERE id = ?"
                                cursor.execute(db_query, [annotation_data['id']])
                                row = cursor.fetchone()
                                    
                                if row:
                                    # Found matching record in database
                                    columns = [column[0] for column in cursor.description]
                                    db_data = dict(zip(columns, row))
                                        
                                    print(f"Database record found: {db_data}")
                                        
                                    # Set arrowStart and arrowEnd from database if not already set
                                    if ('arrowStart' not in annotation_data or not annotation_data['arrowStart']) and \
                                    db_data.get('arrow_start_x') is not None and db_data.get('arrow_start_y') is not None:
                                        annotation_data['arrowStart'] = [db_data['arrow_start_x'], db_data['arrow_start_y']]
                                        print(f"Using arrow start from database: {annotation_data['arrowStart']}")
                                        
                                    if ('arrowEnd' not in annotation_data or not annotation_data['arrowEnd']) and \
                                    db_data.get('arrow_end_x') is not None and db_data.get('arrow_end_y') is not None:
                                        annotation_data['arrowEnd'] = [db_data['arrow_end_x'], db_data['arrow_end_y']]
                                        print(f"Using arrow end from database: {annotation_data['arrowEnd']}")
                                        
                                    # Get other fields if needed
                                    if db_data.get('user_name') and not annotation_data.get('userName', '').strip():
                                        annotation_data['userName'] = db_data['user_name']
                                        
                                    if db_data.get('text_content') and not annotation_data.get('text', '').strip():
                                        annotation_data['text'] = db_data['text_content']
                                        
                                    if db_data.get('font_size') and not annotation_data.get('fontSize'):
                                        annotation_data['fontSize'] = db_data['font_size']
                                        
                                    # Map other fields
                                    field_mappings = {
                                        'arrow_color': 'arrowColor',
                                        'text_color': 'textColor',
                                        'border_color': 'borderColor'
                                    }
                                    
                                    for db_field, annot_field in field_mappings.items():
                                        if db_field in db_data and db_data[db_field] and annot_field not in annotation_data:
                                            annotation_data[annot_field] = db_data[db_field]
                                else:
                                    print(f"No database record found for callout ID: {annotation_data['id']}")
                                    
                                conn.close()
                            except Exception as e:
                                print(f"Database error retrieving callout: {e}")
                                traceback.print_exc()
                            
                        # Ensure we have required fields with defaults if needed
                        if 'arrowStart' not in annotation_data or not annotation_data['arrowStart']:
                            # Default arrow start if not found (left of text box)
                            annotation_data['arrowStart'] = [rect.x0 - 50, rect.y0 + rect.height/2]
                            print(f"Using default arrowStart: {annotation_data['arrowStart']}")
                            
                        if 'arrowEnd' not in annotation_data or not annotation_data['arrowEnd']:
                            # Default arrow end (left edge of text box)
                            annotation_data['arrowEnd'] = [rect.x0, rect.y0 + rect.height/2]
                            print(f"Using default arrowEnd: {annotation_data['arrowEnd']}")
                            
                        if 'textColor' not in annotation_data:
                            annotation_data['textColor'] = 'red'
                            
                        if 'arrowColor' not in annotation_data:
                            annotation_data['arrowColor'] = 'red'
                            
                        if 'borderColor' not in annotation_data:
                            annotation_data['borderColor'] = 'red'

                    content = annot.info.get('content', '')

                    # Handle specific annotation types
                    if annotation_data['type'] == 'polyline':
                        # Get vertices for polyline
                        vertices = annot.vertices
                        if vertices:
                            # Convert tuple vertices to dict with x, y coordinates
                            annotation_data['points'] = [
                                {'x': vertex[0], 'y': vertex[1]} 
                                for vertex in vertices
                            ]
                                
                            # Also update the path for fabric.js
                            points = annotation_data['points']
                            if points:
                                path = f"M {points[0]['x']} {points[0]['y']}"
                                for point in points[1:]:
                                    path += f" L {point['x']} {point['y']}"
                                annotation_data['path'] = path

                            # Determine if it's a cloud or freeDraw based on content or shape characteristics
                            content_lower = annotation_data['content'].lower()
                            subject_lower = annot.info.get('subject', '').lower()
                                
                            # Check for cloud annotation by content or subject
                            if "cloud" in content_lower or "cloud" in subject_lower:
                                annotation_data['type'] = 'cloud'
                                print(f"Identified cloud annotation from content: {annotation_data['id']}")
                                
                            # Check for freeDraw annotation based on content
                            elif any(term in content_lower for term in ["freedraw", "free draw"]) or any(term in subject_lower for term in ["freedraw", "free draw"]):
                                annotation_data['type'] = 'freeDraw'
                                print(f"Identified freeDraw annotation from content: {annotation_data['id']}")
                                
                            # If not identified by content, analyze shape characteristics
                            else:
                                # Calculate the area of the bounding box
                                area = rect.width * rect.height
                                    
                                # Calculate the perimeter of the shape
                                perimeter = 0
                                for i in range(len(points)-1):
                                    dx = points[i+1]['x'] - points[i]['x']
                                    dy = points[i+1]['y'] - points[i]['y']
                                    perimeter += (dx**2 + dy**2)**0.5
                                    
                                # Check if the shape is closed
                                first_point = points[0]
                                last_point = points[-1]
                                dx = last_point['x'] - first_point['x']
                                dy = last_point['y'] - first_point['y']
                                is_closed = (dx**2 + dy**2)**0.5 < 20  # Threshold for "closedness"
                                    
                                # Cloud detection - closed shape with reasonable perimeter-to-area ratio
                                if area > 0 and is_closed and perimeter / area < 0.5:
                                    annotation_data['type'] = 'cloud'
                                    print(f"Identified cloud annotation from shape analysis: {annotation_data['id']}")
                                # FreeDraw detection - many vertices or high perimeter-to-area ratio
                                elif len(vertices) > 30 or (area > 0 and perimeter / area > 1.0):
                                    annotation_data['type'] = 'freeDraw'
                                    print(f"Identified freeDraw annotation from analysis: {annotation_data['id']}")
                                
                                # For debugging
                                print(f"Annotation type: {annotation_data['type']}, Vertices: {len(vertices)}, Content: '{content_lower}'")
                    
                    elif annotation_data['type'] == 'text':
                        # Handle text annotations - ensure they have valid coordinates
                        # If coordinates are invalid, set reasonable defaults
                        if annotation_data['x1'] < 0 or annotation_data['y1'] < 0:
                            # Set default position in the center of the page
                            page_rect = page.rect
                            annotation_data.update({
                                'x1': page_rect.width / 2,
                                'y1': page_rect.height / 2,
                                'x2': page_rect.width / 2 + 100,  # Default width of 100
                                'y2': page_rect.height / 2 + 50,  # Default height of 50
                                'width': 100,
                                'height': 50
                            })
                        
                        # Skip text annotations with empty content
                        if not annotation_data['content'].strip():
                            print(f"Skipping text annotation with empty content: {annotation_data['id']}")
                            continue
                    
                    # REMOVE THIS BLOCK - it's now moved above
                    # elif annotation_data['type'] in ['highlight', 'underline', 'strikeout']:
                    #     annotation_data['lineAnnotations'] = [{
                    #         'left': rect.x0,
                    #         'top': rect.y0,
                    #         'width': rect.width,
                    #         'height': rect.height
                    #     }]
                    #     print(f"Added lineAnnotations for {annotation_data['type']}: {annotation_data['lineAnnotations']}")

                    if hasattr(annot, 'colors'):
                        stroke_color = annot.colors.get('stroke')
                        if stroke_color:
                            annotation_data['stroke'] = f'rgb({int(stroke_color[0]*255)}, {int(stroke_color[1]*255)}, {int(stroke_color[2]*255)})'
                    
                    if hasattr(annot, 'border'):
                        annotation_data['strokeWidth'] = annot.border.get('width', 1)

                    # Add default stroke color if none is set
                    if 'stroke' not in annotation_data:
                        annotation_data['stroke'] = 'rgb(255, 0, 0)'  # Default red color

                    page_annotations.append(annotation_data)
                
                if page_annotations:
                    page_key = str(page_num + 1)
                    if page_key in combined_annotations_by_page:
                        combined_annotations_by_page[page_key].extend(page_annotations)
                    else:
                        combined_annotations_by_page[page_key] = page_annotations
                
            # Create a clean PDF without annotations
            if clean_pdf_base64 is None:
                clean_doc = fitz.open(stream=pdf_stream, filetype="pdf")
                for page in clean_doc:
                    for annot in page.annots():
                        page.delete_annot(annot)
                    
                clean_pdf_bytes = clean_doc.write()
                clean_pdf_base64 = base64.b64encode(clean_pdf_bytes).decode('utf-8')
                clean_doc.close()

            doc.close()
            # clean_doc.close()

        print("Extracted annotations from default PDF:", combined_annotations_by_page)

        return {
            'annotations': combined_annotations_by_page,
            'cleanPdfContent': clean_pdf_base64,
            'message': 'Annotations extracted successfully from default PDF'
        }, None

    except Exception as e:
        print(f"Error extracting annotations from local file: {str(e)}")
        import traceback
        traceback.print_exc() 
        return None, str(e)





# def extract_annotations_from_local_files():
#     try:
        # pdf_ids = app.config.get('CURRENT_PDF_IDS', ['b2b61b57-b148-4bd8-82c0-aff62449edf2', '671daf2e-6e84-4f43-bb95-3535e06df314'])
        
        # if not pdf_ids:
        #     return None, "No PDF IDs provided"
        # pdf_urls = [
        #     "http://idmsdemo.vishwatechnologies.com/Temp/b2b61b57-b148-4bd8-82c0-aff62449edf2.pdf",
        #     "http://idmsdemo.vishwatechnologies.com/Temp/671daf2e-6e84-4f43-bb95-3535e06df314.pdf"
        # ]
        
#         # existing_files = []
#         # for file_path in local_files:
#         #     if os.path.exists(file_path):
#         #         existing_files.append(file_path)
#         #         print(f"Found local PDF file: {file_path}")
        
#         # # If no files found, return error
#         # if not existing_files:
#         #     return None, "No local PDF files found"
            
#         # Initialize combined results

#         pdf_url = request.args.get('pdf')
#         document_id = request.args.get('DocumentId')
#         user_id = request.args.get('UserId')
#         combined_annotations_by_page = {}
#         clean_pdf_base64 = None
#         processed_ids = []

#         api_url = "http://localhost:80/api/get-pdf"
#         if pdf_url:
#             api_url += f"?pdf={pdf_url}"

#         # for pdf_id in pdf_ids:
#             # Open the PDF with PyMuPDF
#         print(f"Downloading PDF from: {api_url}")
#         response = requests.get(api_url, verify=False)
#         response.raise_for_status() 
                
#         pdf_stream = io.BytesIO(response.content)
                
#         doc = fitz.open(stream=pdf_stream, filetype="pdf")

#         print(f"Successfully opened PDF")
#         if document_id:
#             processed_ids.append(document_id)
                
#         print(f"Successfully opened PDF with ID ")
#         processed_ids.append(pdf_id)
        
        
            
        
#         # Extract annotations from each page
#         for page_num in range(len(doc)):
#             page = doc[page_num]
#             page_annotations = []
                
#             for annot in page.annots():
#                 annotation_type = annot.type[1].lower()  # Remove leading '/'
#                     # Convert 'freetext' to 'text' type
#                 if annotation_type == 'freetext':
#                         annotation_type = 'text'
#                     # Get basic annotation data
#                 annotation_data = {
#                     'id': str(uuid.uuid4()),
#                     'type': annotation_type,  # Remove leading '/'
#                     'page': page_num + 1,
#                     'content': annot.info.get('content', ''),
#                     'userName': annot.info.get('title', 'Unknown'),
#                     'createdAt': datetime.now().isoformat()
#                 }
#                 title = annot.info.get('title', '')
#                 content = annot.info.get('content', '')

#                 if annotation_type == 'text':
#                         # Try to extract userId from title first
#                     user_id_match = re.search(r'userId:([^;]+)', title)
#                     if user_id_match:
#                         annotation_data['userId'] = user_id_match.group(1)
#                         print(f"Found user ID in title for text annotation: {annotation_data['userId']}")
                        
#                     # Try to extract documentId from title
#                     doc_id_match = re.search(r'documentId:([^;]+)', title)
#                     if doc_id_match:
#                         annotation_data['documentId'] = doc_id_match.group(1)
#                         print(f"Found document ID in title for text annotation: {annotation_data['documentId']}")
#                     # If not found in title or not a text annotation, check content
#                 if 'userId' not in annotation_data:
#                     user_id_match = re.search(r'userId:([^;]+)', content)
#                     if user_id_match:
#                         annotation_data['userId'] = user_id_match.group(1)
#                         content = re.sub(r'userId:[^;]+;', '', content)
                
#                 if 'documentId' not in annotation_data:
#                     doc_id_match = re.search(r'documentId:([^;]+)', content)
#                     if doc_id_match:
#                         annotation_data['documentId'] = doc_id_match.group(1)
#                         content = re.sub(r'documentId:[^;]+;', '', content)
#                 annotation_data['content'] = content.strip()
                
#                 user_id_match = re.search(r'userId:([^;]+)', content)
#                 if user_id_match:
#                     annotation_data['userId'] = user_id_match.group(1)
#                     # Remove the userId part from the content to display clean content to user
#                     content = re.sub(r'userId:[^;]+;', '', content)
                
#                 # Look for documentId in the content
#                 doc_id_match = re.search(r'documentId:([^;]+)', content)
#                 if doc_id_match:
#                     annotation_data['documentId'] = doc_id_match.group(1)
#                     # Remove the documentId part from the content to display clean content to user
#                     content = re.sub(r'documentId:[^;]+;', '', content)
                
#                 # Update content with cleaned version (without IDs)
#                 annotation_data['content'] = content.strip()
#                 # Get annotation rectangle
#                 rect = annot.rect
                
#                 # Skip invalid rectangles (sometimes seen with text annotations)
#                 if rect.x0 < -1000000 or rect.y0 < -1000000:
#                     print(f"Skipping annotation with invalid rectangle: {annotation_data['type']}")
#                     continue
                
#                 annotation_data.update({
#                     'x1': rect.x0,
#                     'y1': rect.y0,
#                     'x2': rect.x1,
#                     'y2': rect.y1,
#                     'width': rect.width,
#                     'height': rect.height
#                 })
#                 subject = annot.info.get('subject', '')
#                 # In your extract_annotations function:
#                 if subject == 'textCallout':
#                     annotation_data['type'] = 'textCallout'
#                     rect = annot.rect
                    
#                     # Get the title and extract metadata from it FIRST
#                     title = annot.info.get('title', '')
                    
#                     # Extract calloutId early to use for database lookup
#                     callout_id_match = re.search(r'calloutId:([^;]+)', title)
#                     if callout_id_match:
#                         annotation_data['id'] = callout_id_match.group(1)
#                         print(f"Found callout ID in title: {annotation_data['id']}")
                        
#                         # Immediately try to get position from database using the found ID
#                         try:
#                             conn = get_db_connection()
#                             cursor = conn.cursor()
                            
#                             db_query = """
#                             SELECT text_left, text_top 
#                             FROM text_callout_annotations 
#                             WHERE id = ?
#                             """
#                             cursor.execute(db_query, [annotation_data['id']])
#                             row = cursor.fetchone()

#                             if row and row[0] is not None and row[1] is not None:
#                                 # Use exact database values
#                                 annotation_data['textLeft'] = float(row[0])
#                                 annotation_data['textTop'] = float(row[1])
#                                 print(f"Using database position - Left: {row[0]}, Top: {row[1]}")
#                             else:
#                                 print("No database position found, using PDF coordinates")
#                                 annotation_data['textLeft'] = float(rect.x0)
#                                 annotation_data['textTop'] = float(rect.y0)
                            
#                             conn.close()
#                         except Exception as e:
#                             print(f"Database error retrieving text position: {e}")
#                             traceback.print_exc()
#                             annotation_data['textLeft'] = float(rect.x0)
#                             annotation_data['textTop'] = float(rect.y0)
#                     else:
#                         # No ID found, use PDF coordinates
#                         annotation_data['textLeft'] = float(rect.x0)
#                         annotation_data['textTop'] = float(rect.y0)
                    
#                     # Set fixed dimensions
#                     annotation_data['textWidth'] = 75
#                     annotation_data['textHeight'] = 14.69
#                     # Remove rectangle coordinates
#                     annotation_data.pop('x1', None)
#                     annotation_data.pop('y1', None)
#                     annotation_data.pop('x2', None)
#                     annotation_data.pop('y2', None)
#                     annotation_data.pop('width', None)
#                     annotation_data.pop('height', None)

#                         # Rest of your existing code...
#                         # Extract the actual text content (cleaned of metadata)
#                     raw_content = annot.info.get('content', '')
#                     cleaned_content = re.sub(r'(userId|documentId|calloutId):[^;]+;', '', raw_content).strip()
#                     annotation_data['text'] = cleaned_content
                        
#                         # Get the title and extract metadata from it
#                     title = annot.info.get('title', '')
                        
#                         # Extract calloutId, userId, documentId from title
#                     callout_id_match = re.search(r'calloutId:([^;]+)', title)
#                     if callout_id_match:
#                             print(f"Found callout ID in title: {annotation_data['id']}")
                    
#                     user_id_match = re.search(r'userId:([^;]+)', title)
#                     if user_id_match:
#                         annotation_data['userId'] = user_id_match.group(1)
#                         print(f"Found user ID in title: {annotation_data['userId']}")
                        
#                     doc_id_match = re.search(r'documentId:([^;]+)', title)
#                     if doc_id_match:
#                         annotation_data['documentId'] = doc_id_match.group(1)
#                         print(f"Found document ID in title: {annotation_data['documentId']}")
                        
#                         # Clean up the userName field if it contains metadata
#                     user_name = annotation_data.get('userName', '')
#                     if user_name and (user_name.startswith('userId:') or ';' in user_name):
#                             # Try to extract a real username from elsewhere or set a default
#                         annotation_data['userName'] = "Anurag Sable"  # Default fallback
                        
#                         # IMPORTANT: Extract arrow coordinates from the PDF annotation
#                         # PyMuPDF stores callout line information in the annotation
#                     if hasattr(annot, 'callout'):
#                         try:
#                             callout_points = annot.callout
#                             if callout_points and len(callout_points) >= 3:
#                                     # First point is typically the arrow start
#                                 annotation_data['arrowStart'] = [callout_points[0].x, callout_points[0].y]
#                                     # Second point is the arrow end / text connection point
#                                 annotation_data['arrowEnd'] = [callout_points[1].x, callout_points[1].y]
#                                 print(f"Extracted arrow points from PDF: start={annotation_data['arrowStart']}, end={annotation_data['arrowEnd']}")
#                         except Exception as e:
#                             print(f"Error extracting callout points: {e}")
                        
#                         # If we have an ID, try to get data from database as backup
#                     if 'id' in annotation_data:
#                         try:
#                             conn = get_db_connection()
#                             cursor = conn.cursor()
                                
#                             # Query the database for this callout
#                             db_query = "SELECT * FROM text_callout_annotations WHERE id = ?"
#                             cursor.execute(db_query, [annotation_data['id']])
#                             row = cursor.fetchone()
                                
#                             if row:
#                                     # Found matching record in database
#                                 columns = [column[0] for column in cursor.description]
#                                 db_data = dict(zip(columns, row))
                                    
#                                 print(f"Database record found: {db_data}")
                                    
#                                     # Set arrowStart and arrowEnd from database if not already set
#                                 if ('arrowStart' not in annotation_data or not annotation_data['arrowStart']) and \
#                                 db_data.get('arrow_start_x') is not None and db_data.get('arrow_start_y') is not None:
#                                     annotation_data['arrowStart'] = [db_data['arrow_start_x'], db_data['arrow_start_y']]
#                                     print(f"Using arrow start from database: {annotation_data['arrowStart']}")
                                    
#                                 if ('arrowEnd' not in annotation_data or not annotation_data['arrowEnd']) and \
#                                 db_data.get('arrow_end_x') is not None and db_data.get('arrow_end_y') is not None:
#                                     annotation_data['arrowEnd'] = [db_data['arrow_end_x'], db_data['arrow_end_y']]
#                                     print(f"Using arrow end from database: {annotation_data['arrowEnd']}")
                                    
#                                 # Get other fields if needed
#                                 if db_data.get('user_name') and not annotation_data.get('userName', '').strip():
#                                     annotation_data['userName'] = db_data['user_name']
                                    
#                                 if db_data.get('text_content') and not annotation_data.get('text', '').strip():
#                                     annotation_data['text'] = db_data['text_content']
                                    
#                                 if db_data.get('font_size') and not annotation_data.get('fontSize'):
#                                     annotation_data['fontSize'] = db_data['font_size']
                                    
#                                     # Map other fields
#                                 field_mappings = {
#                                     'arrow_color': 'arrowColor',
#                                     'text_color': 'textColor',
#                                     'border_color': 'borderColor'
#                                 }
                                
#                                 for db_field, annot_field in field_mappings.items():
#                                     if db_field in db_data and db_data[db_field] and annot_field not in annotation_data:
#                                         annotation_data[annot_field] = db_data[db_field]
#                             else:
#                                 print(f"No database record found for callout ID: {annotation_data['id']}")
                                
#                             conn.close()
#                         except Exception as e:
#                             print(f"Database error retrieving callout: {e}")
#                             traceback.print_exc()
                        
#                         # Ensure we have required fields with defaults if needed
#                     if 'arrowStart' not in annotation_data or not annotation_data['arrowStart']:
#                         # Default arrow start if not found (left of text box)
#                         annotation_data['arrowStart'] = [rect.x0 - 50, rect.y0 + rect.height/2]
#                         print(f"Using default arrowStart: {annotation_data['arrowStart']}")
                        
#                     if 'arrowEnd' not in annotation_data or not annotation_data['arrowEnd']:
#                         # Default arrow end (left edge of text box)
#                         annotation_data['arrowEnd'] = [rect.x0, rect.y0 + rect.height/2]
#                         print(f"Using default arrowEnd: {annotation_data['arrowEnd']}")
                        
#                     if 'textColor' not in annotation_data:
#                         annotation_data['textColor'] = 'red'
                        
#                     if 'arrowColor' not in annotation_data:
#                         annotation_data['arrowColor'] = 'red'
                        
#                     if 'borderColor' not in annotation_data:
#                         annotation_data['borderColor'] = 'red'

#                 content = annot.info.get('content', '')

#                     # Handle specific annotation types
#                 if annotation_data['type'] == 'polyline':
#                         # Get vertices for polyline
#                     vertices = annot.vertices
#                     if vertices:
#                             # Convert tuple vertices to dict with x, y coordinates
#                         annotation_data['points'] = [
#                             {'x': vertex[0], 'y': vertex[1]} 
#                             for vertex in vertices
#                         ]
                            
#                             # Also update the path for fabric.js
#                         points = annotation_data['points']
#                         if points:
#                             path = f"M {points[0]['x']} {points[0]['y']}"
#                             for point in points[1:]:
#                                 path += f" L {point['x']} {point['y']}"
#                             annotation_data['path'] = path

#                             # Determine if it's a cloud or freeDraw based on content or shape characteristics
#                         content_lower = annotation_data['content'].lower()
#                         subject_lower = annot.info.get('subject', '').lower()
                            
#                             # Check for cloud annotation by content or subject
#                         if "cloud" in content_lower or "cloud" in subject_lower:
#                             annotation_data['type'] = 'cloud'
#                             print(f"Identified cloud annotation from content: {annotation_data['id']}")
                            
#                             # Check for freeDraw annotation based on content
#                         elif any(term in content_lower for term in ["freedraw", "free draw"]) or any(term in subject_lower for term in ["freedraw", "free draw"]):
#                             annotation_data['type'] = 'freeDraw'
#                             print(f"Identified freeDraw annotation from content: {annotation_data['id']}")
                            
#                             # If not identified by content, analyze shape characteristics
#                         else:
#                                 # Calculate the area of the bounding box
#                             area = rect.width * rect.height
                                
#                                 # Calculate the perimeter of the shape
#                             perimeter = 0
#                             for i in range(len(points)-1):
#                                 dx = points[i+1]['x'] - points[i]['x']
#                                 dy = points[i+1]['y'] - points[i]['y']
#                                 perimeter += (dx**2 + dy**2)**0.5
                                
#                                 # Check if the shape is closed
#                             first_point = points[0]
#                             last_point = points[-1]
#                             dx = last_point['x'] - first_point['x']
#                             dy = last_point['y'] - first_point['y']
#                             is_closed = (dx**2 + dy**2)**0.5 < 20  # Threshold for "closedness"
                                
#                             # Cloud detection - closed shape with reasonable perimeter-to-area ratio
#                             if area > 0 and is_closed and perimeter / area < 0.5:
#                                 annotation_data['type'] = 'cloud'
#                                 print(f"Identified cloud annotation from shape analysis: {annotation_data['id']}")
#                             # FreeDraw detection - many vertices or high perimeter-to-area ratio
#                             elif len(vertices) > 30 or (area > 0 and perimeter / area > 1.0):
#                                 annotation_data['type'] = 'freeDraw'
#                                 print(f"Identified freeDraw annotation from analysis: {annotation_data['id']}")
                            
#                             # For debugging
#                             print(f"Annotation type: {annotation_data['type']}, Vertices: {len(vertices)}, Content: '{content_lower}'")
                    
#                     elif annotation_data['type'] == 'text':
#                         # Handle text annotations - ensure they have valid coordinates
#                         # If coordinates are invalid, set reasonable defaults
#                         if annotation_data['x1'] < 0 or annotation_data['y1'] < 0:
#                             # Set default position in the center of the page
#                             page_rect = page.rect
#                             annotation_data.update({
#                                 'x1': page_rect.width / 2,
#                                 'y1': page_rect.height / 2,
#                                 'x2': page_rect.width / 2 + 100,  # Default width of 100
#                                 'y2': page_rect.height / 2 + 50,  # Default height of 50
#                                 'width': 100,
#                                 'height': 50
#                             })
                        
#                         # Skip text annotations with empty content
#                         if not annotation_data['content'].strip():
#                             print(f"Skipping text annotation with empty content: {annotation_data['id']}")
#                             continue
                    
#                     elif annotation_data['type'] in ['highlight', 'underline', 'strikeout']:
#                         annotation_data['lineAnnotations'] = [{
#                             'left': rect.x0,
#                             'top': rect.y0,
#                             'width': rect.width,
#                             'height': rect.height
#                         }]

#                     # Add stroke color and width if available
#                     if hasattr(annot, 'colors'):
#                         stroke_color = annot.colors.get('stroke')
#                         if stroke_color:
#                             annotation_data['stroke'] = f'rgb({int(stroke_color[0]*255)}, {int(stroke_color[1]*255)}, {int(stroke_color[2]*255)})'
                    
#                     if hasattr(annot, 'border'):
#                         annotation_data['strokeWidth'] = annot.border.get('width', 1)

#                     # Add default stroke color if none is set
#                     if 'stroke' not in annotation_data:
#                         annotation_data['stroke'] = 'rgb(255, 0, 0)'  # Default red color

#                     page_annotations.append(annotation_data)
                
#                 if page_annotations:
#                     page_key = str(page_num + 1)
#                     if page_key in combined_annotations_by_page:
#                         combined_annotations_by_page[page_key].extend(page_annotations)
#                     else:
#                         combined_annotations_by_page[page_key] = page_annotations
            
#             # Create a clean PDF without annotations
#             if clean_pdf_base64 is None:
#                 clean_doc = fitz.open(stream=pdf_stream, filetype="pdf")
#                 for page in clean_doc:
#                     for annot in page.annots():
#                         page.delete_annot(annot)
                
#                 clean_pdf_bytes = clean_doc.write()
#                 clean_pdf_base64 = base64.b64encode(clean_pdf_bytes).decode('utf-8')
#                 clean_doc.close()

#             doc.close()
#             # clean_doc.close()

#         print("Extracted annotations from default PDF:", combined_annotations_by_page)

#         return {
#             'annotations': combined_annotations_by_page,
#             'cleanPdfContent': clean_pdf_base64,
#             'message': 'Annotations extracted successfully from default PDF'
#         }, None

#     except Exception as e:
#         print(f"Error extracting annotations from local file: {str(e)}")
#         import traceback
#         traceback.print_exc() 
#         return None, str(e)




#=======================================================================================




# @app.route('/api/annotations/extract', methods=['POST'])
# def extract_annotations():
#     try:
#         pdf_file = request.files['file']
#         doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        
#         # Create a new clean document
#         clean_doc = fitz.open()
#         total_annotations = 0
#         annotation_types = {}
#         extracted_annotations = []
        
#         # Process each page
#         for page_num in range(len(doc)):
#             page = doc[page_num]
#             page_annotations = []
            
#             # Create a clean page without annotations
#             clean_page = clean_doc.new_page(width=page.rect.width, height=page.rect.height)
            
#             try:
#                 # Copy page content without annotations
#                 clean_page.show_pdf_page(
#                     clean_page.rect,
#                     doc,
#                     page_num,
#                     clip=page.rect,
#                     keep_proportion=True
#                 )
                
#                 # Get and remove all annotations
#                 annotations = page.annots()
#                 if annotations:
#                     annot_list = list(annotations)
#                     for annot in annot_list:
#                         try:
#                             annot_type = annot.type[1]
#                             total_annotations += 1
#                             annotation_types[annot_type] = annotation_types.get(annot_type, 0) + 1
#                             annot_data = {
#                                 'type': annot_type,
#                                 'page': page_num + 1,
#                                 'content': annot.info.get('content', ''),
#                                 'subject': annot.info.get('subject', ''),
#                                 'createdAt': datetime.now().isoformat(),
#                                 # 'rect': annot.rect.tolist(),
#                                 # 'id': annot.id,
#                                 'userName': annot.info.get('title', 'Unknown User'),
#                                 'color': annot.colors.get('stroke') or annot.colors.get('fill'),
#                                 'x1': annot.rect.x0,
#                                 'y1': annot.rect.y0,
#                                 'x2': annot.rect.x1,
#                                 'y2': annot.rect.y1,
#                                 'width': annot.rect.width,
#                                 'height': annot.rect.height,
#                                 'isExisting': True
#                             }
#                             page_annotations.append(annot_data)
#                             page.delete_annot(annot)
#                         except Exception as e:
#                             print(f"Error removing annotation: {str(e)}")
#                             continue
                
#                 if page_annotations:
#                     extracted_annotations.append({str(page_num + 1): page_annotations})
                
#                 # Clean any remaining image artifacts
#                 clean_page.clean_contents()
                
#             except Exception as e:
#                 print(f"Error processing page {page_num + 1}: {str(e)}")
#                 continue
        
#         # Save the clean PDF to a buffer
#         output_buffer = io.BytesIO()
#         clean_doc.save(output_buffer, 
#                       garbage=4,      # Maximum garbage collection
#                       deflate=True,   # Compress streams
#                       clean=True)     # Clean content streams
        
#         # Convert to base64
#         pdf_base64 = base64.b64encode(output_buffer.getvalue()).decode()
        
#         # Close documents
#         doc.close()
#         clean_doc.close()
        
#         # Return the results
#         return jsonify({
#             'success': True,
#             'pdfContent': pdf_base64,
#             'metadata': {
#                 'totalAnnotations': total_annotations,
#                 'annotationTypes': annotation_types,
#                 'removedAnnotations': total_annotations
#             },
#             'annotations': extracted_annotations
#         })
#         print(f'sended annotations to frontend {extracted_annotations}')
        
#     except Exception as e:
#         print(f"Error in extract_annotations: {str(e)}")
#         if 'doc' in locals():
#             doc.close()
#         if 'clean_doc' in locals():
#             clean_doc.close()
#         return jsonify({'error': str(e)}), 500


# @app.route('/api/annotations/apply', methods=['POST'])
# def apply_annotations():
#     try:
#         data = request.get_json()
#         if not data or 'pdfContent' not in data or 'annotations' not in data:
#             return jsonify({'error': 'Missing required data'}), 400

#         pdf_content = base64.b64decode(data['pdfContent'])
#         annotations = data['annotations']
        
#         # Create a new PDF document from the clean content
#         doc = fitz.open(stream=pdf_content, filetype="pdf")
        
#         try:
#             # Apply filtered annotations
#             for page_num, page_annotations in annotations.items():
#                 page = doc[int(page_num) - 1]
#                 for annotation in page_annotations:
#                     try:
#                         # Skip unwanted annotation types
#                         annot_type = annotation.get('type', '').lower()
#                         if annot_type in ['cloud', 'stamp', 'signature']:
#                             continue
                            
#                         # Apply the annotation based on its type
#                         if annot_type == 'highlight':
#                             rect = fitz.Rect(annotation['rect'])
#                             annot = page.add_highlight_annot(rect)
#                         elif annot_type == 'underline':
#                             rect = fitz.Rect(annotation['rect'])
#                             annot = page.add_underline_annot(rect)
#                         elif annot_type == 'strikeout':
#                             rect = fitz.Rect(annotation['rect'])
#                             annot = page.add_strikeout_annot(rect)
                        
#                         # Set annotation metadata if created
#                         if annot:
#                             annot.set_info({
#                                 'title': annotation.get('author', ''),
#                                 'subject': annotation.get('subject', ''),
#                                 'content': annotation.get('content', '')
#                             })
#                             annot.update()
                            
#                     except Exception as e:
#                         print(f"Error applying annotation: {e}")
#                         continue

#             # Save the modified PDF to a buffer
#             output_buffer = io.BytesIO()
#             doc.save(output_buffer)
#             doc.close()
            
#             # Convert to base64
#             pdf_base64 = base64.b64encode(output_buffer.getvalue()).decode()
            
#             return jsonify({
#                 'pdfContent': pdf_base64,
#                 'message': 'Annotations applied successfully'
#             })
            
#         finally:
#             if doc:
#                 doc.close()
                
#     except Exception as e:
#         print(f"Error in apply_annotations: {str(e)}")
#         traceback.print_exc()
#         return jsonify({'error': str(e)}), 500

# def handle_text_annotation(page, annotation):
#     """Handle text-layer annotations (highlight, underline, strike-through)"""
#     rect = fitz.Rect(annotation['rect'])
    
#     if annotation['type'] == 'Highlight':
#         annot = page.add_highlight_annot(rect)
#         annot.set_colors(stroke=(1, 1, 0))  # Yellow highlight
#     elif annotation['type'] == 'Underline':
#         annot = page.add_underline_annot(rect)
#         annot.set_colors(stroke=(1, 0, 0))  # Red underline
#     elif annotation['type'] == 'StrikeOut':
#         annot = page.add_strikeout_annot(rect)
#         annot.set_colors(stroke=(1, 0, 0))  # Red strike-through
    
#     return annot

# def handle_image_annotation(page, annotation):
#     """Handle image-based annotations (stamps, signatures)"""
#     if 'imageData' in annotation:
#         img_bytes = base64.b64decode(annotation['imageData'])
#         rect = fitz.Rect(annotation['rect'])
#         page.insert_image(rect, stream=img_bytes)
        
#         # Add metadata annotation
#         annot = page.add_stamp_annot(rect)
#         return annot
#     return None

# def handle_drawing_annotation(page, annotation):
#     """Handle Fabric.js drawing annotations"""
#     if 'path' in annotation:
#         # Convert Fabric.js path to PDF path
#         pdf_path = []
#         for cmd in annotation['path']:
#             if cmd[0] == 'M':
#                 pdf_path.append(f"{cmd[1]} {cmd[2]} m")
#             elif cmd[0] == 'L':
#                 pdf_path.append(f"{cmd[1]} {cmd[2]} l")
#             elif cmd[0] == 'Q':
#                 pdf_path.append(f"{cmd[1]} {cmd[2]} {cmd[3]} {cmd[4]} c")
        
#         # Create ink annotation
#         annot = page.add_ink_annot([pdf_path])
#         annot.set_colors(stroke=annotation.get('color', (0, 0, 0)))
#         annot.set_border(width=annotation.get('strokeWidth', 1))
#         return annot
#     return None

# def save_annotations_to_json(doc_id, annotations):
#     """Save annotations to JSON file"""
#     filename = f"annotations_{doc_id}.json"
#     with open(filename, 'w') as f:
#         json.dump(annotations, f)

# def load_annotations_from_json(doc_id):
#     """Load annotations from JSON file"""
#     try:
#         filename = f"annotations_{doc_id}.json"
#         with open(filename, 'r') as f:
#             return json.load(f)
#     except FileNotFoundError:
#         return {}



#====================================================================================




#=======================================================================================

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
#             subject = annot.info.get('subject', '').lower()
            
#             print(f"Annotation Type: {annot_type}")
#             print(f"Subject: {subject}")
#             print(f"Rectangle: {rect}")
            
#             # Determine the true type based on subject
#             if 'cloud' in subject:
#                 true_type = 'cloud'
#             elif 'signature' in subject:
#                 true_type = 'signature'
#             elif 'stamp' in subject:
#                 true_type = 'stamp'
#             else:
#                 # Use the standard mapping
#                 true_type = self.annotation_types.get(annot_type, 'unknown')
            
#             print(f"True type determined: {true_type}")
            
#             # Basic annotation data
#             annotation_data = {
#                 'id': str(uuid.uuid4()),
#                 'type': true_type,
#                 'page': page_num,
#                 'userName': annot.info.get('title', 'Unknown User'),
#                 'content': annot.info.get('content', ''),
#                 'subject': subject,
#                 'createdAt': datetime.now().isoformat()
#             }

#             # Handle coordinates and dimensions
#             if rect:
#                 annotation_data.update({
#                     'x1': rect.x0,
#                     'y1': rect.y0,
#                     'x2': rect.x1,
#                     'y2': rect.y1,
#                     'width': rect.width,
#                     'height': rect.height
#                 })

#             # Get annotation color
#             if hasattr(annot, 'colors'):
#                 colors = annot.colors
#                 if colors:
#                     stroke_color = colors.get('stroke') or colors.get('fill')
#                     if stroke_color:
#                         annotation_data['color'] = f"rgb({int(stroke_color[0]*255)}, {int(stroke_color[1]*255)}, {int(stroke_color[2]*255)})"
#                     else:
#                         annotation_data['color'] = 'rgb(255, 0, 0)'  # Default red color
#             else:
#                 annotation_data['color'] = 'rgb(255, 0, 0)'  # Default red color

#             # Process specific annotation types
#             if true_type in ['stamp', 'signature']:
#                 print(f"Processing {true_type} annotation...")
#                 try:
#                     # Get the annotation's appearance stream as an image
#                     pix = annot.get_pixmap()
#                     if pix:
#                         # Convert pixmap to PNG and encode as base64
#                         img_data = pix.tobytes("png")
#                         annotation_data['imageData'] = base64.b64encode(img_data).decode('utf-8')
#                         print(f"Successfully extracted {true_type} image data")
#                     else:
#                         # Try alternative method - get AP stream
#                         ap = annot.get_ap()
#                         if ap:
#                             pix = ap.get_pixmap()
#                             if pix:
#                                 img_data = pix.tobytes("png")
#                                 annotation_data['imageData'] = base64.b64encode(img_data).decode('utf-8')
#                                 print(f"Successfully extracted {true_type} image data from AP stream")
#                             else:
#                                 print(f"No image data found for {true_type}")
#                 except Exception as e:
#                     print(f"Error extracting {true_type} image: {str(e)}")
#                     print(traceback.format_exc())

#             elif true_type in ['highlight', 'underline', 'strikeout']:
#                 # For text markup annotations, ensure we have the correct coordinates
#                 quads = annot.vertices
#                 if quads:
#                     # Get the bounding box of all quads
#                     x0 = min(q.x for quad in quads for q in quad)
#                     y0 = min(q.y for quad in quads for q in quad)
#                     x1 = max(q.x for quad in quads for q in quad)
#                     y1 = max(q.y for quad in quads for q in quad)
#                     annotation_data.update({
#                         'x1': x0,
#                         'y1': y0,
#                         'x2': x1,
#                         'y2': y1,
#                         'width': x1 - x0,
#                         'height': y1 - y0
#                     })

#             elif true_type in ['cloud', 'freeDraw']:
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

#             print("Successfully processed annotation")
#             return annotation_data

#         except Exception as e:
#             print(f"Error processing annotation: {str(e)}")
#             print(traceback.format_exc())
#             return None



# def remove_annotations_from_pdf(doc):
#     """Remove all annotations from a PDF using a more aggressive approach."""
#     print("\n=== Removing annotations from PDF (aggressive method) ===")
#     total_removed = 0
    
#     try:
#         # First approach: Try to remove annotations page by page
#         for page_num in range(len(doc)):
#             page = doc[page_num]
#             annots = list(page.annots())
            
#             if annots:
#                 print(f"Page {page_num + 1}: Found {len(annots)} annotations")
                
#                 # Log annotation types
#                 annot_types = [a.type[1] for a in annots]
#                 print(f"Annotation types: {annot_types}")
                
#                 # Remove annotations in reverse order to avoid index issues
#                 for i in range(len(annots) - 1, -1, -1):
#                     try:
#                         page.delete_annot(annots[i])
#                         total_removed += 1
#                     except Exception as e:
#                         print(f"Error deleting annotation: {str(e)}")
        
#         # Second approach: Create a new document and copy content without annotations
#         if total_removed == 0 or any(len(list(doc[i].annots())) > 0 for i in range(len(doc))):
#             print("First approach didn't remove all annotations, trying second approach...")
            
#             # Create a new document
#             new_doc = fitz.open()
            
#             # For each page in the original document
#             for page_num in range(len(doc)):
#                 page = doc[page_num]
                
#                 # Create a new page with the same dimensions
#                 new_page = new_doc.new_page(
#                     width=page.rect.width,
#                     height=page.rect.height
#                 )
                
#                 # Copy the page content (without annotations)
#                 new_page.show_pdf_page(
#                     new_page.rect,
#                     doc,
#                     page_num,
#                     clip=None,
#                     keep_proportion=True,
#                     overlay=False
#                 )
            
#             # Replace the original document with the new one
#             doc.delete_pages(range(len(doc)))
#             doc.insert_pdf(new_doc)
#             new_doc.close()
            
#             # Count total annotations removed
#             total_removed = sum(len(list(doc[i].annots())) for i in range(len(doc)))
#             print(f"Second approach completed, removed approximately {total_removed} annotations")
        
#         # Third approach: If annotations still exist, try a different method
#         if any(len(list(doc[i].annots())) > 0 for i in range(len(doc))):
#             print("Second approach didn't remove all annotations, trying third approach...")
            
#             # Save to temporary file and reload (sometimes this clears problematic annotations)
#             temp_buffer = io.BytesIO()
#             doc.save(temp_buffer, garbage=4, deflate=True, clean=True)
#             temp_buffer.seek(0)
            
#             # Close the original document
#             doc.close()
            
#             # Reload from the temporary buffer
#             doc = fitz.open(stream=temp_buffer, filetype="pdf")
            
#             # Count remaining annotations
#             remaining = sum(len(list(doc[i].annots())) for i in range(len(doc)))
#             print(f"Third approach completed, {remaining} annotations remain")
        
#         # Final verification
#         remaining_annots = sum(len(list(doc[i].annots())) for i in range(len(doc)))
#         if remaining_annots > 0:
#             print(f"WARNING: {remaining_annots} annotations still remain after all removal attempts")
#         else:
#             print("All annotations successfully removed")
        
#         return total_removed
        
#     except Exception as e:
#         print(f"Error in remove_annotations_from_pdf: {str(e)}")
#         print(traceback.format_exc())
#         return 0

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

#=============================================================================================

# @app.route('/api/annotations/extract', methods=['POST'])
# def extract_pdf_annotations():
#     try:
#         if 'file' not in request.files:
#             return jsonify({'error': 'No file provided'}), 400
            
#         pdf_file = request.files['file']
#         doc = None
#         output_buffer = io.BytesIO()
        
#         try:
#             # Read file content into memory
#             file_content = pdf_file.read()
#             input_buffer = io.BytesIO(file_content)
            
#             # Open PDF from memory buffer
#             doc = fitz.open(stream=input_buffer, filetype="pdf")
#             total_pages = len(doc)
            
#             # Extract annotations first
#             annotations_by_page = {}
#             total_annotations = 0
            
#             # Process each page
#             for page_num in range(total_pages):
#                 page = doc[page_num]
#                 page_annotations = []
                
#                 # Get page dimensions
#                 page_rect = page.rect
#                 page_width = page_rect.width
#                 page_height = page_rect.height
                
#                 # Get all annotations on the page
#                 annots = list(page.annots())
                
#                 print(f"Page {page_num + 1}: Found {len(annots)} annotations")
                
#                 # Process regular annotations
#                 for annot in annots:
#                     try:
#                         annot_type = annot.type[1]
#                         rect = annot.rect
                        
#                         if not rect:
#                             continue
                            
#                         print(f"Processing annotation type: {annot_type}")
                        
#                         # Get annotation content and subject
#                         content = annot.info.get('content', '')
#                         subject = annot.info.get('subject', '')
#                         title = annot.info.get('title', '')
                        
#                         print(f"  Content: {content}")
#                         print(f"  Subject: {subject}")
#                         print(f"  Title: {title}")
                        
#                         # Map annotation types
#                         annotation_type = map_annotation_type(annot_type)
                        
#                         # Better detection for stamps and signatures
#                         # Check content, subject, and title for keywords
#                         keywords = content.lower() + " " + subject.lower() + " " + title.lower()
                        
#                         if 'stamp' in keywords or 'seal' in keywords:
#                             annotation_type = 'stamp'
#                             print(f"  Detected as stamp based on keywords")
#                         elif 'sign' in keywords or 'signature' in keywords:
#                             annotation_type = 'signature'
#                             print(f"  Detected as signature based on keywords")

                        
                        
#                         # Handle special cases for polyline annotations (freeDraw or cloud)
#                         if annot_type == 'PolyLine' or annot_type == 'Polygon':
#                             vertices = annot.vertices if hasattr(annot, 'vertices') else []
#                             if vertices:
#                                 # Check if it's a cloud (closed shape) or freeDraw
#                                 if len(vertices) > 4 and vertices[0] == vertices[-1]:
#                                     annotation_type = 'cloud'
#                                 else:
#                                     annotation_type = 'freeDraw'
                                    
#                                 # Convert vertices to path format for fabric.js
#                                 path = []
#                                 for i, vertex in enumerate(vertices):
#                                     if isinstance(vertex, (tuple, list)):
#                                         x, y = vertex
#                                     else:
#                                         x, y = vertex.x, vertex.y
                                    
#                                     if i == 0:
#                                         path.append(['M', x, y])
#                                     else:
#                                         path.append(['L', x, y])
                        
#                         # Get annotation color
#                         color = None
#                         if hasattr(annot, 'colors') and annot.colors:
#                             color_values = annot.colors.get('stroke') or annot.colors.get('fill')
#                             if color_values:
#                                 color = f"rgb({int(color_values[0]*255)}, {int(color_values[1]*255)}, {int(color_values[2]*255)})"
                        
#                         # Create base annotation data
#                         annotation_data = {
#                             'id': str(uuid.uuid4()),
#                             'type': annotation_type,
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
#                             'color': color or 'rgb(255, 0, 0)',  # Default to red
#                             'strokeWidth': annot.border_width if hasattr(annot, 'border_width') else 1
#                         }

#                         # Process specific annotation types
#                         if annotation_type == 'cloud':
#                             annotation_data = process_cloud_annotation(annot, annotation_data)
#                         elif annotation_type == 'stamp':
#                             annotation_data = process_stamp_annotation(annot, annotation_data)
#                         elif annotation_type == 'signature':
#                             annotation_data = process_signature_annotation(annot, annotation_data)
#                         elif annotation_type == 'freeDraw' or annotation_type == 'cloud':
#                             if 'path' in locals():
#                                 annotation_data['path'] = path
#                         elif annotation_type in ['highlight', 'underline', 'strikeout']:
#                             # For text markup annotations, handle vertices differently
#                             line_annotations = []
                            
#                             # Try different approaches to get the highlight rectangles
#                             if hasattr(annot, 'vertices') and annot.vertices:
#                                 try:
#                                     # First approach: Try to use vertices directly
#                                     quads = annot.vertices
                                    
#                                     # Check if quads is a list of points or a list of quads
#                                     if quads and isinstance(quads[0], (list, tuple)) and len(quads[0]) == 4:
#                                         # It's a list of quads
#                                         for quad in quads:
#                                             # Each quad has 4 points
#                                             x_values = [p[0] if isinstance(p, (list, tuple)) else p for p in quad]
#                                             y_values = [p[1] if isinstance(p, (list, tuple)) else p for p in quad]
                                            
#                                             left = min(x_values)
#                                             top = min(y_values)
#                                             width = max(x_values) - left
#                                             height = max(y_values) - top
                                            
#                                             line_annotations.append({
#                                                 'left': left,
#                                                 'top': top,
#                                                 'width': width,
#                                                 'height': height
#                                             })
#                                     elif quads:
#                                         line_annotations.append({
#                                             'left': rect.x0,
#                                             'top': rect.y0,
#                                             'width': rect.width,
#                                             'height': rect.height
#                                         })
#                                 except Exception as e:
#                                     print(f"Error processing text markup vertices: {str(e)}")
#                                     line_annotations.append({
#                                         'left': rect.x0,
#                                         'top': rect.y0,
#                                         'width': rect.width,
#                                         'height': rect.height
#                                     })
#                                 annotation_data['lineAnnotations'] = line_annotations
#                             else:
#                                 # If no vertices, use the rectangle
#                                 line_annotations.append({
#                                     'left': rect.x0,
#                                     'top': rect.y0,
#                                     'width': rect.width,
#                                     'height': rect.height
#                                 })
                                
#                             annotation_data['lineAnnotations'] = line_annotations
#                         elif annotation_type == 'circle':
#                             # For circle annotations, calculate radius
#                             width = rect.width
#                             height = rect.height
#                             radius = min(width, height) / 2
#                             annotation_data['radius'] = radius

#                         page_annotations.append(annotation_data)
#                         total_annotations += 1
                        
#                     except Exception as e:
#                         print(f"Error processing annotation: {str(e)}")
#                         continue

#                 # Store annotations if any were found
#                 if page_annotations:
#                     annotations_by_page[str(page_num + 1)] = page_annotations

#             # Now remove all annotations from the PDF
#             print("\n=== Removing annotations from PDF ===")
#             total_removed = 0
            
#             try:
#                 # First approach: Remove annotations page by page
#                 for page_num in range(len(doc)):
#                     page = doc[page_num]
#                     annots = list(page.annots())
                    
#                     if annots:
#                         print(f"Page {page_num + 1}: Found {len(annots)} annotations to remove")
                        
#                         # Remove annotations in reverse order to avoid index issues
#                         for i in range(len(annots) - 1, -1, -1):
#                             try:
#                                 annot = annots[i]
#                                 annot_type = annot.type[1]
                                
#                                 # Special handling for cloud annotations (PolyLine or Polygon)
#                                 if annot_type in ['PolyLine', 'Polygon']:
#                                     try:
#                                         # Check if it's a cloud annotation
#                                         vertices = annot.vertices if hasattr(annot, 'vertices') else []
#                                         is_cloud = (len(vertices) > 4 and vertices[0] == vertices[-1]) or ('cloud' in annot.info.get('subject', '').lower())
                                        
#                                         if is_cloud:
#                                             print(f"Removing cloud annotation from page {page_num + 1}")
#                                             # Force clean the appearance stream
#                                             if hasattr(annot, 'set_ap'):
#                                                 annot.set_ap("")
                                            
#                                             # Force update the annotation
#                                             if hasattr(annot, 'update'):
#                                                 annot.update()
                                            
#                                             # Delete the annotation
#                                             page.delete_annot(annot)
                                            
#                                             # Immediately clean the page contents
#                                             page.clean_contents()
                                            
#                                             total_removed += 1
#                                             continue
#                                     except Exception as e:
#                                         print(f"Error removing cloud annotation: {str(e)}")
                                
#                                 # For stamps and signatures, we need special handling
#                                 elif annot_type in ['Stamp', 'Text']:
#                                     try:
#                                         # Clear the annotation's appearance stream
#                                         if hasattr(annot, 'set_ap'):
#                                             annot.set_ap("")
#                                         # Set the annotation's rectangle to zero size
#                                         if hasattr(annot, 'set_rect'):
#                                             annot.set_rect(fitz.Rect(0, 0, 0, 0))
                                        
#                                         # Delete the annotation
#                                         page.delete_annot(annot)
#                                         total_removed += 1
#                                     except Exception as e:
#                                         print(f"Error removing stamp/signature annotation: {str(e)}")
                                
#                                 # Handle other annotation types
#                                 else:
#                                     try:
#                                         page.delete_annot(annot)
#                                         total_removed += 1
#                                     except Exception as e:
#                                         print(f"Error removing annotation: {str(e)}")
                            
#                             except Exception as e:
#                                 print(f"Error processing annotation for removal: {str(e)}")
                    
#                     else:
#                         # Clean up after processing all annotations on the page
#                         try:
#                             page.clean_contents()
#                             page.apply_redactions()
#                         except Exception as e:
#                             print(f"Error cleaning page contents: {str(e)}")
                
#                 # Additional cleanup: Refresh all page contents
#                 for page_num in range(len(doc)):
#                     page = doc[page_num]
#                     page.clean_contents()  # Clean up any orphaned content
#                     page.apply_redactions()  # Apply any pending redactions
                
#                 # Save with cleanup options
#                 doc.save(output_buffer, 
#                         garbage=4,  # Maximum garbage collection
#                         deflate=True,  # Compress streams
#                         clean=True,  # Clean unused elements
#                         pretty=False,  # Don't prettify PDF
#                         linear=True)  # Optimize for web viewing
                
#             except Exception as e:
#                 print(f"Error during annotation removal: {str(e)}")
#                 # Still try to save the document even if there was an error
#                 doc.save(output_buffer, garbage=True, deflate=True, clean=True)

           
#             # output_buffer = io.BytesIO()
#             doc.save(output_buffer, garbage=True, deflate=True, clean=True)
#             modified_pdf_content = output_buffer.getvalue()
            
#             # Create response data
#             response_data = {
#                 'annotations': annotations_by_page,
#                 'metadata': {
#                     'totalPages': total_pages,
#                     'totalAnnotations': total_annotations,
#                     'removedAnnotations': total_removed,
#                     'pagesInfo': {
#                         str(i+1): {
#                             'width': doc[i].rect.width,
#                             'height': doc[i].rect.height,
#                             'rotation': doc[i].rotation
#                         } for i in range(total_pages)
#                     }
#                 },
#                 'pdfContent': base64.b64encode(modified_pdf_content).decode('utf-8')
#             }
            
#             print(f"Successfully processed {total_annotations} annotations and removed {total_removed}")
#             return jsonify(response_data)
            
#         except Exception as e:
#             print(f"Error in processing: {str(e)}")
#             return jsonify({'error': f'Error processing annotations: {str(e)}'}), 500
#         finally:
#             if doc:
#                 doc.close()
#             # Clean up memory buffers
#             if 'input_buffer' in locals():
#                 input_buffer.close()
#             if 'output_buffer' in locals():
#                 output_buffer.close()
                
#     except Exception as e:
#         print(f"General error: {str(e)}")
#         return jsonify({'error': str(e)}), 500

# def process_stamp_annotation(annot, annotation_data):
#     """Process stamp annotation and extract image data before removal."""
#     try:
#         # Extract data first
#         annotation_data = extract_stamp_data(annot, annotation_data)
        
#         # Clean up the annotation
#         if hasattr(annot, 'set_ap'):
#             annot.set_ap("")
#         if hasattr(annot, 'set_rect'):
#             annot.set_rect(fitz.Rect(0, 0, 0, 0))
            
#         return annotation_data
#     except Exception as e:
#         print(f"Error processing stamp annotation: {str(e)}")
#         return annotation_data

# def process_signature_annotation(annot, annotation_data):
#     """Process signature annotation and extract image data before removal."""
#     try:
#         # Extract data first
#         annotation_data = extract_signature_data(annot, annotation_data)
        
#         # Clean up the annotation
#         if hasattr(annot, 'set_ap'):
#             annot.set_ap("")
#         if hasattr(annot, 'set_rect'):
#             annot.set_rect(fitz.Rect(0, 0, 0, 0))
            
#         return annotation_data
#     except Exception as e:
#         print(f"Error processing signature annotation: {str(e)}")
#         return annotation_data
# def extract_stamp_data(annot, annotation_data):
#     """Extract image data from stamp annotation."""
#     try:
#         # Get the appearance stream
#         ap = annot.get_ap()
#         if ap:
#             try:
#                 # Try to get image from appearance stream
#                 pix = ap.get_pixmap()
#                 if pix:
#                     img_data = pix.tobytes("png")
#                     annotation_data['imgSrc'] = f"data:image/png;base64,{base64.b64encode(img_data).decode('utf-8')}"
#             except Exception as e:
#                 print(f"Failed to extract stamp image: {str(e)}")
        
#         # Add stamp-specific properties
#         annotation_data.update({
#             'type': 'stamp',
#             'x1': annot.rect.x0,
#             'y1': annot.rect.y0,
#             'x2': annot.rect.x1,
#             'y2': annot.rect.y1,
#             'width': annot.rect.width,
#             'height': annot.rect.height
#         })
#         return annotation_data
#     except Exception as e:
#         print(f"Error in extract_stamp_data: {str(e)}")
#         return annotation_data

# def extract_signature_data(annot, annotation_data):
#     """Extract image data from signature annotation."""
#     try:
#         # Get the appearance stream
#         ap = annot.get_ap()
#         if ap:
#             try:
#                 # Try to get image from appearance stream
#                 pix = ap.get_pixmap()
#                 if pix:
#                     img_data = pix.tobytes("png")
#                     annotation_data['dataURL'] = f"data:image/png;base64,{base64.b64encode(img_data).decode('utf-8')}"
#             except Exception as e:
#                 print(f"Failed to extract signature image: {str(e)}")
        
#         # Add signature-specific properties
#         annotation_data.update({
#             'type': 'signature',
#             'x1': annot.rect.x0,
#             'y1': annot.rect.y0,
#             'x2': annot.rect.x1,
#             'y2': annot.rect.y1,
#             'width': annot.rect.width,
#             'height': annot.rect.height
#         })
#         return annotation_data
#     except Exception as e:
#         print(f"Error in extract_signature_data: {str(e)}")
#         return annotation_data



# def process_cloud_annotation(annot, annotation_data):
#     """Process cloud annotation and extract path data before removal."""
#     try:
#         # First extract the data
#         if hasattr(annot, 'vertices') and annot.vertices:
#             vertices = annot.vertices
#             if vertices:
#                 path = []
#                 for i, vertex in enumerate(vertices):
#                     if isinstance(vertex, (tuple, list)):
#                         x, y = vertex
#                     else:
#                         x, y = vertex.x, vertex.y
#                     if i == 0:
#                         path.append(['M', x, y])
#                     else:
#                         path.append(['L', x, y])
                
#                 annotation_data.update({
#                     'path': path,
#                     'type': 'cloud',
#                     'strokeWidth': annot.border_width if hasattr(annot, 'border_width') else 2,
#                     'closePath': True
#                 })

#         # Don't try to remove here - let the main removal process handle it
#         return annotation_data
#     except Exception as e:
#         print(f"Error processing cloud annotation: {str(e)}")
#         return annotation_data

# # Update the annotation removal section in extract_pdf_annotations:
# try:
#     # First approach: Remove annotations page by page
#     for page_num in range(len(doc)):
#         page = doc[page_num]
#         annots = list(page.annots())
        
#         if annots:
#             print(f"Page {page_num + 1}: Found {len(annots)} annotations to remove")
            
#             # Remove annotations in reverse order to avoid index issues
#             for i in range(len(annots) - 1, -1, -1):
#                 try:
#                     annot = annots[i]
#                     annot_type = annot.type[1]
                    
#                     # Special handling for cloud annotations
#                     if annot_type in ['PolyLine', 'Polygon']:
#                         try:
#                             # Force clean the appearance stream
#                             if hasattr(annot, 'set_ap'):
#                                 annot.set_ap("")
                            
#                             # Force update the annotation
#                             annot.update()
                            
#                             # Delete the annotation
#                             page.delete_annot(annot)
                            
#                             # Immediately clean the page contents
#                             page.clean_contents()
                            
#                             total_removed += 1
#                             print(f"Removed cloud annotation from page {page_num + 1}")
#                             continue
#                         except Exception as e:
#                             print(f"Error removing cloud annotation: {str(e)}")
                    
#                     # Handle other annotation types
#                     try:
#                         page.delete_annot(annot)
#                         total_removed += 1
#                     except Exception as e:
#                         print(f"Error removing annotation: {str(e)}")
                
#                 except Exception as e:
#                     print(f"Error processing annotation for removal: {str(e)}")
            
#             # Clean up after processing all annotations on the page
#             try:
#                 page.clean_contents()
#                 page.apply_redactions()
#             except Exception as e:
#                 print(f"Error cleaning page contents: {str(e)}")

#     # Final cleanup of the document
#     doc.save(output_buffer, 
#             garbage=4,
#             deflate=True,
#             clean=True,
#             pretty=False,
#             linear=True)
    
# except Exception as e:
#     print(f"Error during annotation removal: {str(e)}")

# # Add a new function for freeDraw annotations:
# def process_freedraw_annotation(annot, annotation_data):
#     """Process freeDraw annotation and extract path data before removal."""
#     try:
#         # Extract path data
#         if hasattr(annot, 'vertices') and annot.vertices:
#             vertices = annot.vertices
#             if vertices:
#                 path = []
#                 for i, vertex in enumerate(vertices):
#                     if isinstance(vertex, (tuple, list)):
#                         x, y = vertex
#                     else:
#                         x, y = vertex.x, vertex.y
#                     if i == 0:
#                         path.append(['M', x, y])
#                     else:
#                         path.append(['L', x, y])
                
#                 annotation_data.update({
#                     'path': path,
#                     'type': 'freeDraw',
#                     'strokeWidth': annot.border_width if hasattr(annot, 'border_width') else 1,
#                     'closePath': False  # freeDraw doesn't need to be closed
#                 })

#         # Remove the freeDraw annotation
#         try:
#             page = annot.parent
#             if page:
#                 # Clear the appearance stream
#                 if hasattr(annot, 'set_ap'):
#                     annot.set_ap("")
                
#                 # Delete the annotation
#                 page.delete_annot(annot)
#                 print("Successfully removed freeDraw annotation")
#         except Exception as e:
#             print(f"Error removing freeDraw annotation: {str(e)}")
            
#         return annotation_data
#     except Exception as e:
#         print(f"Error processing freeDraw annotation: {str(e)}")
#         return annotation_data

# @app.route('/api/annotations/remove_remaining', methods=['POST'])
# def remove_remaining_annotations():
#     try:
#         if 'file' not in request.files:
#             return jsonify({'error': 'No file provided'}), 400
            
#         pdf_file = request.files['file']
#         doc = None
#         output_buffer = io.BytesIO()
        
#         try:
#             # Read file content into memory
#             file_content = pdf_file.read()
#             input_buffer = io.BytesIO(file_content)
            
#             # Open PDF from memory buffer
#             doc = fitz.open(stream=input_buffer, filetype="pdf")
#             total_pages = len(doc)
#             total_removed = 0
            
#             # Focus specifically on cloud, stamp, and signature annotations
#             for page_num in range(total_pages):
#                 page = doc[page_num]
#                 annots = list(page.annots())
                
#                 if annots:
#                     print(f"Second pass - Page {page_num + 1}: Found {len(annots)} annotations")
                    
#                     # Remove annotations in reverse order to avoid index issues
#                     for i in range(len(annots) - 1, -1, -1):
#                         try:
#                             annot = annots[i]
#                             annot_type = annot.type[1]
                            
#                             # Check if it's a cloud, stamp, or signature annotation
#                             is_cloud = (annot_type in ['PolyLine', 'Polygon']) and hasattr(annot, 'vertices')
#                             is_stamp = annot_type == 'Stamp' or ('stamp' in annot.info.get('subject', '').lower())
#                             is_signature = 'sign' in annot.info.get('subject', '').lower()
                            
#                             if is_cloud or is_stamp or is_signature:
#                                 print(f"Second pass - Removing {annot_type} annotation from page {page_num + 1}")
                                
#                                 # Try to clear the appearance stream
#                                 if hasattr(annot, 'set_ap'):
#                                     annot.set_ap("")
                                
#                                 # Delete the annotation
#                                 page.delete_annot(annot)
                                
#                                 # Clean the page contents immediately
#                                 page.clean_contents()
                                
#                                 total_removed += 1
#                         except Exception as e:
#                             print(f"Second pass - Error removing annotation: {str(e)}")
                
#                 # Clean up the page
#                 page.clean_contents()
#                 page.apply_redactions()
            
#             # Final cleanup of the document
#             doc.save(output_buffer, 
#                     garbage=4,
#                     deflate=True,
#                     clean=True,
#                     pretty=False,
#                     linear=True)
            
#             modified_pdf_content = output_buffer.getvalue()
            
#             print(f"Second pass - Successfully removed {total_removed} annotations")
            
#             # Return the cleaned PDF
#             return jsonify({
#                 'success': True,
#                 'removedAnnotations': total_removed,
#                 'pdfContent': base64.b64encode(modified_pdf_content).decode('utf-8')
#             })
            
#         except Exception as e:
#             print(f"Second pass - Error in processing: {str(e)}")
#             return jsonify({'error': f'Error removing annotations: {str(e)}'}), 500
#         finally:
#             if doc:
#                 doc.close()
#             # Clean up memory buffers
#             if 'input_buffer' in locals():
#                 input_buffer.close()
#             if 'output_buffer' in locals():
#                 output_buffer.close()
                
#     except Exception as e:
#         print(f"Second pass - General error: {str(e)}")
#         return jsonify({'error': str(e)}), 500




# def map_annotation_type(pymupdf_type):
#     type_mapping = {
#         'Square': 'square',
#         'Circle': 'circle',
#         'Line': 'line',
#         'FreeText': 'text',
#         'Text': 'text',
#         'Highlight': 'highlight',
#         'Underline': 'underline',
#         'StrikeOut': 'strikeout',
#         'Ink': 'freeDraw',
#         'Stamp': 'stamp',
#         'Polygon': 'cloud',
#         'PolyLine': 'freeDraw'
#     }
#     return type_mapping.get(pymupdf_type, 'unknown')




#=============================================================================================







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
    """Validates and normalizes color values for PyMuPDF."""
    # Handle None case
    if color is None:
        return (0, 0, 0)  # Default to black
    
    # Handle named colors
    if isinstance(color, str):
        color_map = {
            'red': (1, 0, 0),
            'green': (0, 1, 0),
            'blue': (0, 0, 1),
            'black': (0, 0, 0),
            'white': (1, 1, 1),
            'yellow': (1, 1, 0),
            'cyan': (0, 1, 1),
            'magenta': (1, 0, 1)
        }
        return color_map.get(color.lower(), (0, 0, 0))
    
    # Handle tuple/list case
    if isinstance(color, (tuple, list)) and len(color) == 3:
        # Ensure values are floats between 0 and 1
        return tuple(max(0, min(float(c), 1)) for c in color)
    
    # Default fallback
    return (0, 0, 0)

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
