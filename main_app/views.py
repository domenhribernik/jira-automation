from apscheduler.triggers.interval import IntervalTrigger
from django.shortcuts import render
from django.http import JsonResponse
from lib.lib import *

in_memory_handler = setup_logging()
# Create your views here.
def home(request):
    return render(request, 'main_app/index.html')

def run_task(request, task_name):
    if request.method == "POST":
        if task_name == "import_lapsed_clients":
            import_lapsed_clients("Lapsed")
        elif task_name == "check_for_new_orders":
            check_for_new_orders("New Web Orders")
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

def get_scheduled_tasks(request):
    jobs = scheduler.get_jobs()
    task_status = {}

    interval = 1

    for job in jobs:
        if isinstance(job.trigger, IntervalTrigger):
            interval = job.trigger.interval.days
        task_status[job.name] = {
            "status": 1,  # 1 for active, 0 for inactive
            "next_run": job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else None,
            "interval": interval
        }

    return JsonResponse(task_status)

def schedule_task(request, task_name): #TODO Make a state for active, and make this function like a switch on and off
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            interval_days = int(data.get('intervalDays'))
        except json.JSONDecodeError:
            return JsonResponse({"message": "Invalid JSON"}, status=400)

        if task_name == "import_lapsed_clients":
            job = scheduler.add_job(
                import_lapsed_clients,
                'interval',
                minutes=interval_days,
                args=["Lapsed"],
                id=f"job_{task_name}",
                replace_existing=True
            )
        elif task_name == "check_for_new_orders":
            job = scheduler.add_job(
                check_for_new_orders,
                'interval',
                days=interval_days,
                args=["New Web Orders"],
                id=f"job_{task_name}",
                replace_existing=True
            )
        elif task_name == "schedule_emails":
            job = scheduler.add_job(
                schedule_emails,
                'interval',
                days=interval_days,
                args=[3, "In Progress"], #? 3 days delay
                id=f"job_{task_name}",
                replace_existing=True
            )
        else:
            return JsonResponse({"message": "Invalid task name"}, status=400)
        
        return JsonResponse({
            "status": True,
            "next_run": job.next_run_time.strftime("%Y-%m-%d %H:%M:%S"),
            "interval": interval_days
        })
    return JsonResponse({"message": "Invalid request"}, status=400)

def delete_scheduled_task(request, task_name):
    if request.method == "POST":
        job = scheduler.get_job(f"job_{task_name}")
        logging.info(f"Deleting job {job}")
        if job:
            scheduler.remove_job(job.id)
            return JsonResponse({
                "status": False,
                "next_run:" : "Not scheduled"
            })
        else:
            return JsonResponse({
                "error": f"Job '{task_name}' not found"
            }, status=404)
        
    return JsonResponse({"message": "Invalid request"}, status=400)

def view_logs(request):
    try:
        with open("Logs/app.log", "r") as log_file:
            log_content = log_file.read()
    except FileNotFoundError:
        log_content = "No logs available."

    return render(request, "main_app/logs.html", {"log_content": log_content})