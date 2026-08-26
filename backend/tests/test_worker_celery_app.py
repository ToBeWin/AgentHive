import unittest

from app.workers.celery_app import celery_app


class WorkerCeleryAppTests(unittest.TestCase):
    def test_media_generation_task_is_registered(self):
        celery_app.loader.import_default_modules()

        self.assertIn("agenthive.media.execute_generation_job", celery_app.tasks)
        self.assertIn("agenthive.media.poll_generation_job", celery_app.tasks)
        self.assertEqual("json", celery_app.conf.task_serializer)
        self.assertEqual("json", celery_app.conf.result_serializer)


if __name__ == "__main__":
    unittest.main()
