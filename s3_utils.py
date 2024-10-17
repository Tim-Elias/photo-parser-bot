import aioboto3
from botocore.exceptions import ClientError
from botocore.client import Config
import os
import logging
from utils import hash_string
from dotenv import load_dotenv

load_dotenv()

class S3Handler:
    def __init__(self):
        self.bucket_name = os.getenv('BUCKET_NAME')
        self.endpoint_url = os.getenv('ENDPOINT_URL')
        self.region_name = os.getenv('REGION_NAME')
        self.aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')

    """async def _create_s3_client(self):
        session = aioboto3.Session()
        return session.client(
                's3',
                endpoint_url=os.getenv('ENDPOINT_URL'),
                region_name=os.getenv('REGION_NAME'),
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                config=Config(s3={'addressing_style': 'path'})
            )"""


    async def check_object_exists(self, object_key: str) -> bool:
        async with aioboto3.Session().client(
                    's3',
                    endpoint_url=self.endpoint_url,
                    region_name=self.region_name,
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key) as s3:
            try:
                # Проверяем наличие объекта
                await s3.head_object(Bucket=self.bucket_name, Key=object_key)
                logging.info(f"Object {object_key} exists.")
                return True  # Объект существует
            except ClientError as e:
                # Проверка на ошибку 404 Not Found
                if e.response['Error']['Code'] == '404':
                    logging.info(f"Object {object_key} does not exist.")
                    return False  # Объект не существует
                else:
                    # Логируем другие ошибки
                    logging.error(f"Error checking object {object_key}: {e}")
                    return False  # Возвращаем False при других ошибках

    async def post_s3(self, data, ext):
        hash_value = hash_string(data, 'sha256')
        s3_file_key = f'{hash_value}.{ext}'

        if not await self.check_object_exists(s3_file_key):
            logging.debug(f"Загрузка объекта '{s3_file_key}' в ведро '{self.bucket_name}'")
            async with aioboto3.Session().client(
                    's3',
                    endpoint_url=self.endpoint_url,
                    region_name=self.region_name,
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key) as s3:
                try:
                    await s3.put_object(
                        Bucket=self.bucket_name,
                        Key=s3_file_key,
                        Body=data.encode('utf-8'),
                        ContentType='application/json'
                    )
                    logging.info(f"Объект {s3_file_key} успешно загружен в S3.")
                    return {'status': 'created', 'data': s3_file_key}, s3_file_key
                except Exception as e:
                    logging.error(f"Ошибка при загрузке в S3: {e}")
                    return {'status': 'error', 'error': str(e)}
        else:
            logging.info(f"Объект {s3_file_key} уже существует в S3.")
            return {'status': 'exists', 'data': s3_file_key}, s3_file_key
