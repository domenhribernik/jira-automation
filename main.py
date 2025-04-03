from lib.lib import *

def main():
    setup_logging()
    scheduler.add_job(
        import_lapsed_clients,
        'interval',
        minutes=30,
        args=["Lapsed", "Lapsed"]
    )
    scheduler.add_job(
        check_for_new_orders,
        'interval',
        minutes=40,
        args=["New Web Orders", "New Web Orders"]
    )
    scheduler.add_job(
        schedule_emails,
        'interval',
        minutes=50,
        args=[3, "In Progress"] #? 3 days delay
    )
    print_task_list()

    while True:
        user_input = input("Enter a command (Tasks, Delete, Exit): \n").strip().lower()
        if user_input == "tasks" or user_input == "t":
            print_task_list()
        elif user_input == "delete" or user_input == "d":
            print_task_list()
            job_id = input("Enter the Job ID to delete: \n").strip()
            scheduler.remove_job(job_id)
            print(f"Job {job_id} deleted.")
        elif user_input == "exit" or user_input == "e":
            print("Exiting program...")
            scheduler.shutdown()
            break
        else:
            print("Unknown command. Try 'tasks', 'delete' or 'exit'.") 
    
if __name__ == "__main__":
    main()
