from apscheduler.triggers.interval import IntervalTrigger
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from apscheduler.jobstores.base import JobLookupError
import tempfile
from lib.lib import *

in_memory_handler = setup_logging()
NEWLY_SCHEDULED_TASKS = []

def home(request):
    return render(request, 'main_app/index.html')

def test_send_email(request):
    if request.method == 'POST':
        try:

            data = json.loads(request.body)
            
            logging.info(f"Received data: {data}")

            result = send_email("test email", "message", "webadmin@cwcyprus.com")
            return JsonResponse({
                'status': 'success',
                'result': result,
                'message': 'Data processed successfully!',
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST requests are allowed.'
    }, status=405)

def import_data(request):
    if request.method == 'POST':
        file = request.FILES.get('file')
        if not file:
            return JsonResponse({'status': False, 'message': 'No file uploaded'})
        
        sheet_name = request.POST.get('sheetname')
        if not sheet_name:
            return JsonResponse({'status': False, 'message': 'No sheet name selected'})
        
        file_extension = os.path.splitext(file.name)[1].lower()
        if file_extension not in ['.xlsx', '.csv']:
            return JsonResponse({'status': False, 'message': 'Invalid file type. Only .xlsx and .csv are supported'})
        
        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
            for chunk in file.chunks():
                temp_file.write(chunk)
            temp_file_path = temp_file.name
        
        try:   
            status, message = import_file_to_google_sheets(
                file_path=temp_file_path,
                spreadsheet_name=sheet_name,
                expected_columns=["Name", "Last Payment Date", "Last Payment Amount", "Email", "Telephone 1"],
                sheet_name=sheet_name
            )
            
            os.unlink(temp_file_path)
            
            return JsonResponse({'status': status, 'message': message})
            
        except Exception as e:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            return JsonResponse({'status': False, 'message': f'Error: {str(e)}'})
    
    return JsonResponse({'status': status, 'message': message})

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

def get_scheduled_tasks(request):
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


def get_sub_tasks(request, category):
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
            seconds = data.get('seconds_delay', None)
            interval_args = {unit: value}
        except json.JSONDecodeError:
            return JsonResponse({"message": "Invalid JSON"}, status=400)

        logging.info(seconds)
        kwargs = {}
        if seconds is not None:
            kwargs['next_run_time'] = datetime.now() + timedelta(seconds=int(seconds))

        logging.info(kwargs)

        if task_name == "import_lapsed_clients":
            job = scheduler.add_job(
                import_lapsed_clients,
                'interval',
                 **interval_args,
                args=["Lapsed", "Lapsed"],
                id=f"job_{task_name}",
                replace_existing=True,
                **kwargs
            )
        elif task_name == "check_for_new_orders":
            job = scheduler.add_job(
                check_for_new_orders,
                'interval',
                 **interval_args,
                args=["New Web Orders", "New Web Orders"],
                id=f"job_{task_name}",
                replace_existing=True,
                **kwargs
            )
        elif task_name == "schedule_emails":
            job = scheduler.add_job(
                schedule_emails,
                'interval',
                 **interval_args,
                args=[3, "In Progress"], #? 3 days delay
                id=f"job_{task_name}",
                replace_existing=True,
                **kwargs
            )
        else:
            return JsonResponse({"message": "Invalid task name"}, status=400)
        
        return JsonResponse({
            'status': True,
            'id': job.id,
            'next_run': job.next_run_time.strftime("%Y-%m-%d %H:%M:%S"),
            'interval_value': value,
            'interval_unit': unit
        })
    return JsonResponse({"message": "Invalid request"}, status=400)

@require_POST
def send_email_early(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body)
        sub_task_name = data.get('sub_task_name')

        if not sub_task_name:
            return JsonResponse({"error": "Missing sub_task_name"}, status=400)

        job_id = sub_task_name
        job = scheduler.get_job(job_id)

        if not job:
            return JsonResponse({"error": f"No job found with ID {job_id}"}, status=404)

        send_email(*job.args)
        scheduler.remove_job(job.id)
        logging.info(f"Email job for {job_id} triggered early.")
        return JsonResponse({"status": "success", "message": f"Email job for {job_id} triggered early."})
    except JobLookupError:
        return JsonResponse({"error": "Job not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def delete_scheduled_task(request, task_name):
    if request.method == "POST":
        job = scheduler.get_job(task_name) or scheduler.get_job(f"job_{task_name}")
        if not job:
            return JsonResponse({
                "error": f"Job '{task_name}' not found"
            }, status=404)
        scheduler.remove_job(job.id)
        
        return JsonResponse({
            "status": False,
            "id": job.id,
            "next_run:" : "Not scheduled"
        })
        
    return JsonResponse({"message": "Invalid request"}, status=400)


def view_logs(request):
    try:
        with open("logs/app.log", "r", encoding="utf-8") as log_file:
            log_content = log_file.read()
    except FileNotFoundError:
        log_content = "No logs available."
    except UnicodeDecodeError:
        # Fallback if UTF-8 fails
        try:
            with open("logs/app.log", "r", encoding="latin-1") as log_file:
                log_content = log_file.read()
        except Exception as e:
            log_content = f"Error reading log file: {str(e)}"

    return render(request, "main_app/logs.html", {"log_content": log_content})
