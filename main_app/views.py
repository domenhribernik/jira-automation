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

def schedule_task(request, task_name):
    if request.method == "POST":
        job_exists, job = print_full_task(task_name)
        if job_exists:
            return JsonResponse({
                "status": 0,
                "message": f"Task {task_name} deleted successfully!",
            })
        if task_name == "import_lapsed_clients":
            scheduler.add_job(
                import_lapsed_clients,
                'interval',
                days=1,
                args=["Lapsed"]
            )
            log("info", print_full_task("import_lapsed_clients"))
        elif task_name == "check_for_new_orders":
            log("info", "Checking for new orders")
        elif task_name == "schedule_emails":
            log("info", "Scheduling emails")
        else:
            return JsonResponse({"message": "Invalid task name"}, status=400)

        return JsonResponse({
            "status": 1,
            "countdown": 1234,
        })
    return JsonResponse({"message": "Invalid request"}, status=400)