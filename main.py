from lib.lib import *

def main():
    setup_logging()
    job_exists, job = print_full_task("import_lapsed_clients")
    if job_exists:
        print(job.id, " ", job.name, " ", job.next_run_time)
    scheduler.add_job(
        import_lapsed_clients,
        'interval',
        seconds=30,
        args=["Lapsed"]
    )
    scheduler.add_job(
        check_for_new_orders,
        'interval',
        seconds=40,
        args=["New Web Orders"]
    )
    scheduler.add_job(
        schedule_emails,
        'interval',
        seconds=50,
        args=[3, "In Progress"] #? 3 days delay
    )
    print_task_list()
    job_exists, job = print_full_task("import_lapsed_clients")
    if job_exists:
        print(job.id, " ", job.name, " ", job.next_run_time.strftime("%Y-%m-%d %H:%M:%S"))

    # while True: # TODO Make a django and html ui for this
    #     user_input = input("Enter a command (Tasks, Delete, Exit): \n").strip().lower()
    #     if user_input == "tasks" or user_input == "t":
    #         print_task_list()
    #     elif user_input == "delete" or user_input == "d":
    #         print_task_list()
    #         job_id = input("Enter the Job ID to delete: \n").strip()
    #         scheduler.remove_job(job_id)
    #         print(f"Job {job_id} deleted.")
    #     elif user_input == "exit" or user_input == "e":
    #         print("Exiting program...")
    #         scheduler.shutdown()
    #         break
    #     else:
    #         print("Unknown command. Try 'tasks', 'delete' or 'exit'.") 
    
if __name__ == "__main__":
    main()
