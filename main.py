import os
from io import FileIO
from fastapi import FastAPI, UploadFile, File, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import sys
import uuid
from celery import Celery
import celery.exceptions
from config import *


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
celery_app = Celery("tasks", broker=f"pyamqp://{CELERY_USERNAME}:{CELERY_PASSWORD}@{CELERY_SERVER}//")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# StreamHandler for the console
stream_handler = logging.StreamHandler(sys.stdout)
log_formatter = logging.Formatter("%(asctime)s [%(processName)s: %(process)d] [%(threadName)s: %(thread)d] [%(levelname)s] %(name)s: %(message)s")
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)

logger.info('API is starting up')


'''
@app.get("/")
async def root():
    return {"message": "Hello World"}
'''

class XMRGDateRangeRequest(BaseModel):
    start_date: str
    end_date: str
    email_address: str
    geospatial_file: bytes

@app.post("/v1/api/xmrgdaterange")
async def xmrgdaterange(    start_date: str,
                            end_date: str,
                            email_address: str,
                            file: UploadFile,
                            response: Response
):
    response_message = {}
    logger.info(f"xmrgdaterange: {start_date} {end_date} {email_address}")
    try:
        task_id = uuid.uuid4()
        working_path = os.path.join(WORKING_DIR, str(task_id))
        logger.info(f"Creating task directory: {working_path}")
        if os.path.exists(working_path):
            logger.warning(f"Task directory: {working_path} already exists, deleting.")
            os.remove(working_path)
        os.makedirs(working_path)
        fullfile_path = os.path.join(working_path, file.filename)
        with open(fullfile_path, "wb") as geo_obj:
            logger.info(f"Saving geospatial file: {fullfile_path}")
            contents = file.file.read()
            geo_obj.write(contents)
            try:
                result = celery_app.send_task('xmrg_celery_app.xmrg_task',
                                       args=[start_date,
                                             end_date,
                                             file.filename,
                                             contents, email_address],
                                        task_id=task_id)
                response_message = {
                    'message': "Job Posted. The results will be emailed when the processing has completed."}
            except Exception as e:
                response.status_code = 500
                response_message = {'message': "Error with the job posting or request."}
            finally:
                file.file.close()

    except (FileIO, Exception) as e:
        response.status_code = 500
        logger.error(e)
        response_message = {'message': "Error with the job posting or request."}
    finally:
        return response_message
