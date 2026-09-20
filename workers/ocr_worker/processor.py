import os
import tempfile

import pymupdf

from .paddleocr_engine import PaddleEngine

from backend.storage.minio_client import (
    get_file,
    put_json,
)


class OCRProcessor:

    def __init__(self):
        self.engine = PaddleEngine()

    def process(
        self,
        invoice_id,
        object_name,
    ):
        extension = os.path.splitext(
            object_name
        )[1].lower()

        fd, input_path = tempfile.mkstemp(
            suffix=extension
        )

        os.close(fd)

        try:
            get_file(
                object_name,
                input_path,
            )

            pages = []

            if extension == ".pdf":

                document = pymupdf.open(
                    input_path
                )

                try:

                    for page_number, page in enumerate(
                        document,
                        start=1,
                    ):

                        fd, image_path = tempfile.mkstemp(
                            suffix=".png"
                        )

                        os.close(fd)

                        try:

                            pixmap = page.get_pixmap(
                                matrix=pymupdf.Matrix(
                                    2,
                                    2,
                                ),
                                alpha=False,
                            )

                            pixmap.save(
                                image_path
                            )

                            ocr_result = (
                                self.engine.predict(
                                    image_path
                                )
                            )

                            pages.append(
                                {
                                    "page_number": page_number,
                                    "text": ocr_result,
                                }
                            )

                        finally:

                            if os.path.exists(
                                image_path
                            ):
                                os.remove(
                                    image_path
                                )

                finally:
                    document.close()

            else:

                ocr_result = (
                    self.engine.predict(
                        input_path
                    )
                )

                pages.append(
                    {
                        "page_number": 1,
                        "text": ocr_result,
                    }
                )

            result = {
                "invoice_id": invoice_id,
                "file_name": os.path.basename(
                    object_name
                ),
                "pages": pages,
            }

            put_json(
                f"ocr/{invoice_id}/ocr.json",
                result,
            )

            return result

        finally:

            if os.path.exists(
                input_path
            ):
                os.remove(
                    input_path
                )