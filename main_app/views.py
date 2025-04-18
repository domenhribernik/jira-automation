from apscheduler.triggers.interval import IntervalTrigger
from django.shortcuts import render
from django.http import JsonResponse
from .models import ScheduledTask
from lib.lib import *

in_memory_handler = setup_logging()
NEWLY_SCHEDULED_TASKS = []
# Create your views here.
def home(request):
    return render(request, 'main_app/index.html')

def run_task(request, task_name):
    if request.method == "POST":
        if task_name == "import_lapsed_clients":
            import_lapsed_clients("Lapsed", "Lapsed")
        elif task_name == "check_for_new_orders":
            check_for_new_orders("New Web Orders", "New Web Orders")
        elif task_name == "schedule_emails":
            schedule_emails(3, "In Progress")  # 3 days delay
        elif task_name == "print_task_list":
            print_task_list()
        else:
            return JsonResponse({"message": "Invalid task name"}, status=400)

        logs = in_memory_handler.get_logs()
        logs_list = logs.split('#')
        if logs_list[-1] == '':
            logs_list.pop()

        return JsonResponse({
            "message": f"{task_name} started successfully!",
            "logs": logs_list,  # Include logs in the response
        })
    return JsonResponse({"message": "Invalid request"}, status=400)

def get_scheduled_tasks_from_memory(request):
    if request.method == "GET":
        jobs = scheduler.get_jobs()
        task_status = {}

        for job in jobs:
            if isinstance(job.trigger, IntervalTrigger):
                interval = job.trigger.interval

                if interval.days > 0:
                    interval_value = interval.days
                    interval_unit = "days"
                elif interval.seconds % 3600 == 0:
                    interval_value = interval.seconds // 3600
                    interval_unit = "hours"
                elif interval.seconds % 60 == 0:
                    interval_value = interval.seconds // 60
                    interval_unit = "minutes"
                else:
                    interval_value = interval.seconds
                    interval_unit = "seconds"
            else:
                interval_value = None
                interval_unit = None

            task_status[job.id] = {
                "status": 1,  # 1 for active, 0 for inactive
                "id": job.id,
                "name": job.name,
                "interval_value": interval_value,
                "interval_unit": interval_unit,
                "next_run": job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else None
            }

    return JsonResponse(task_status)


def get_scheduled_tasks(request):
    data = {}
    if request.method == "GET":
        tasks = ScheduledTask.objects.all()

        for task in tasks:
            data[task.task_id] = {
                "name": task.name,
                "status": bool(task.status),
                "interval": f"{task.interval_value} {task.interval_unit}",
                "next_run": task.next_run.strftime("%Y-%m-%d %H:%M:%S") if task.next_run else "Not scheduled"
            }

    return JsonResponse(data)


def get_sub_tasks(request, category): #TODO if app reboots the scheduled emails are lost
    if request.method == "GET":
        jobs = scheduler.get_jobs()
        task_list = {} 

        for job in jobs:
            if not job.id.startswith(category + "_"):
                continue

            task_list[job.id] = {
                "status": 1,  # 1 for active, 0 for inactive
                "id": job.id,
                "next_run": job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else None
            }
        logging.info(f"Task list: {task_list}")
    return JsonResponse(task_list)


def schedule_task(request, task_name):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            value = int(data.get('interval_value'))
            unit = data.get('interval_unit')
            interval_args = {unit: value}
        except json.JSONDecodeError:
            return JsonResponse({"message": "Invalid JSON"}, status=400)

        if task_name == "import_lapsed_clients":
            job = scheduler.add_job(
                import_lapsed_clients,
                'interval',
                 **interval_args,
                args=["New Web Orders", "Lapsed"],
                id=f"job_{task_name}",
                replace_existing=True
            )
        elif task_name == "check_for_new_orders":
            job = scheduler.add_job(
                check_for_new_orders,
                'interval',
                 **interval_args,
                args=["New Web Orders", "New Web Orders"],
                id=f"job_{task_name}",
                replace_existing=True
            )
        elif task_name == "schedule_emails":
            job = scheduler.add_job(
                schedule_emails,
                'interval',
                 **interval_args,
                args=[3, "In Progress"], #? 3 days delay
                id=f"job_{task_name}",
                replace_existing=True
            )
        else:
            return JsonResponse({"message": "Invalid task name"}, status=400)
        
        # Create or update the scheduled task in DB
        task, created = ScheduledTask.objects.update_or_create(
            task_id=f"job_{task_name}",
            defaults={
                'status': 1,
                'name': task_name,
                'next_run': job.next_run_time.strftime("%Y-%m-%d %H:%M:%S"),
                'interval_value': value,
                'interval_unit': unit,
            }
        )
        
        return JsonResponse({
            'status': True,
            'id': job.id,
            'next_run': job.next_run_time.strftime("%Y-%m-%d %H:%M:%S"),
            'interval_value': value,
            'interval_unit': unit
        })
    return JsonResponse({"message": "Invalid request"}, status=400)


def delete_scheduled_task(request, task_name):
    if request.method == "POST":
        job = scheduler.get_job(task_name) or scheduler.get_job(f"job_{task_name}")
        if not job:
            logging.info("Available jobs at time of deletion:")
            for j in scheduler.get_jobs():
                logging.info(j.id)
            return JsonResponse({
                "error": f"Job '{task_name}' not found"
            }, status=404)
        scheduler.remove_job(job.id)
        try:
            task = ScheduledTask.objects.get(name=task_name)
            task.delete()
            return JsonResponse({
                "status": False,
                "id": job.id,
                "next_run:" : "Not scheduled"
            })
        except ScheduledTask.DoesNotExist:
            return JsonResponse({"message": "Failed to delete from db"}, status=400)
        
    return JsonResponse({"message": "Invalid request"}, status=400)


def view_logs(request):
    try:
        with open("Logs/app.log", "r") as log_file:
            log_content = log_file.read()
    except FileNotFoundError:
        log_content = "No logs available."

    return render(request, "main_app/logs.html", {"log_content": log_content})