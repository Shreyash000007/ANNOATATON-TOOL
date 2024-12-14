import base64
import io
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, render_template, send_file, send_from_directory

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/images/<filename>')
def serve_image(filename):
    image_directory = 'C:/PDF/images'  # Path to your image directory
    return send_from_directory(image_directory, filename)

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
        # print(f"PDF data length: {len(pdf_data)}")

        annotations = data.get('annotations', [])

        doc = fitz.open(stream=pdf_data, filetype="pdf")

        for annotation in annotations:
            try:
                page_num = annotation.get("page", 1) - 1
                page = doc.load_page(page_num)

                if annotation["type"] == "text":
                    if all(key in annotation for key in ["x1", "y1", "x2", "y2"]):
                        rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
                        text_annotation = page.add_freetext_annot(rect, annotation["text"])
                        text_annotation.set_info(title=annotation.get("title", ""), subject=annotation.get("subject", ""), content=annotation.get("content", ""))
                        text_annotation.update()
                    else:
                        print(f"Missing coordinates for text annotation: {annotation}")

                elif annotation["type"] == "line":
                    if all(key in annotation for key in ["x1", "y1", "x2", "y2"]):
                        start = fitz.Point(annotation["x1"], annotation["y1"])
                        end = fitz.Point(annotation["x2"], annotation["y2"])
                        page.draw_line(start, end, color=(1, 0, 0), width=annotation.get("strokeWidth", 1))
                        
                    else:
                        print(f"Missing coordinates for line annotation: {annotation}")

                elif annotation["type"] == "highlight":
                    if all(key in annotation for key in ["x1", "y1", "x2", "y2"]):
                        rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
                        highlight_annot = page.add_highlight_annot(rect)
                        highlight_annot.set_opacity(0.5)
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
                        underline_annot = page.add_underline_annot(rect)
                        underline_annot.set_colors(stroke=(1, 0, 0))
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
                        rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
                        strikeout_annot = page.add_strikeout_annot(rect)
                        strikeout_annot.set_colors(stroke=(0, 0, 0))
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
                        rect = fitz.Rect(annotation["x1"], annotation["y1"], annotation["x2"], annotation["y2"])
                        square_annot = page.add_rect_annot(rect)
                        square_annot.set_info(
                            title=annotation.get("title", ""),
                            subject=annotation.get("subject", ""),
                            content=annotation.get("content", "")
                        )
                        default_stroke = validate_and_normalize_color(annotation.get("stroke", [0, 0, 0]))
                        square_annot.set_colors(stroke=default_stroke)
                        square_annot.set_border(width=annotation.get("strokeWidth", 1))
                        square_annot.update()
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
                            circle_annot.update()
                        else:
                            print(f"Invalid radius for circle annotation: {annotation}")
                    else:
                        print(f"Missing data for circle annotation: {annotation}")

                elif annotation["type"] == "cloud":
                    if "path" in annotation:
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
                        path = annotation['path']
                        fitz_path = []
                        for command in path:
                            if command[0] == 'M':
                                fitz_path.append(fitz.Point(command[1], command[2]))
                            elif command[0] == 'Q':
                                fitz_path.append(fitz.Point(command[1], command[2]))
                                fitz_path.append(fitz.Point(command[3], command[4]))
                        page.draw_polyline(fitz_path, color=(0, 0, 0), width=2)
                        x1, y1 = annotation.get("x1", 0), annotation.get("y1", 0)
                        rect = fitz.Rect(x1, y1, x1 + 1, y1 + 1)
                        freeDraw_annot = page.add_freetext_annot(rect, "")
                        freeDraw_annot.set_info(title=annotation.get("title", ""), subject=annotation.get("subject", ""), content=annotation.get("content", ""))
                        freeDraw_annot.update()
                    else:
                        print(f"Missing path data for freeDraw annotation: {annotation}")

            except Exception as e:
                print(f"Error processing annotation {annotation}: {e}")

        output_stream = io.BytesIO()
        doc.save(output_stream)
        output_stream.seek(0)
        doc.close()

        return send_file(output_stream, as_attachment=True, download_name="annotated.pdf", mimetype="application/pdf")

    except Exception as e:
        print(f"Error in save_pdf: {e}")
        return jsonify({"error": "An error occurred while saving the PDF."}), 500

if __name__ == '__main__':
    app.run(debug=True)
