document.addEventListener("DOMContentLoaded", function () {
    fetchTasks();
});

const ALL_TASKS = [
    "import_lapsed_clients",
    "check_for_new_orders",
    "schedule_emails"
];

let taskIntervals = {};

function toggleSubTasks(expandButton, subTaskContainer) {
    subTaskContainer.classList.toggle("visible");
    expandButton.classList.toggle("open");
    subTaskContainer.classList.contains("visible") ? expandButton.innerHTML = '<i class="fas fa-chevron-up"></i>' : expandButton.innerHTML = '<i class="fas fa-chevron-down"></i>';
}

function updateTaskList(taskName, taskData) {
    const logContainer = document.getElementById("taskList");
    if (taskData.status) {
        const entryDiv = document.createElement("div");
        entryDiv.id = taskData.id;
        entryDiv.classList.add("log-entry");
        entryDiv.innerHTML = `<strong>${taskName}:</strong> ${JSON.stringify(taskData)}`;
        logContainer.appendChild(entryDiv);
    }
    else {
        const entryDiv = document.getElementById(taskData.id);
        if (entryDiv) entryDiv.remove();
    }
}

function createTaskElement(taskName, taskData) {
    const taskItem = document.createElement("div");
    taskItem.classList.add("taskScheduleItem");
    taskItem.setAttribute("data-task-name", taskName);

    const statusSpan = document.createElement("span");
    statusSpan.classList.add("status");
    statusSpan.innerText = taskData.status ? "Active" : "Disabled";
    taskData.status ? statusSpan.classList.add("active") : statusSpan.classList.remove("active");

    const label = document.createElement("label");
    label.innerText = taskName.replace(/_/g, " ");

    const intervalInputContainer = document.createElement("div");
    intervalInputContainer.classList.add("intervalInput");
    intervalInputContainer.innerHTML = `
        <select id="intervalUnit" ${ taskData.status ? "disabled" : "" }>
            <option value="days" ${ taskData.interval_unit === "days" ? "selected" : "" }>Days</option>
            <option value="hours" ${ taskData.interval_unit === "hours" ? "selected" : "" }>Hours</option>
            <option value="minutes" ${ taskData.interval_unit === "minutes" ? "selected" : "" }>Minutes</option>
            <option value="seconds" ${ taskData.interval_unit === "seconds" ? "selected" : "" }>Seconds</option>
        </select>
        <input type="number" min="1" value="${ taskData.interval_value ? taskData.interval_value : 1 }" class="intervalValue" ${ taskData.status ? "disabled" : "" } />
    `;

    const countdownSpan = document.createElement("span");
    countdownSpan.classList.add("countdown");
    taskData.status ? countdownToDate(taskName, taskData, countdownSpan) : countdownSpan.innerText = "Not scheduled";
    // countdownSpan.innerText = taskData.status ? taskData.next_run : "Not scheduled";

    const actionButton = document.createElement("button");
    actionButton.classList.add("taskActionBtn");
    actionButton.innerText = taskData.status ? "Deactivate" : "Activate";
    taskData.status ? actionButton.classList.add("deactivate") : actionButton.classList.remove("deactivate");
    actionButton.onclick = () => {
        if (taskData.status) {
            deleteScheduledTask(taskName);
        } else {
            scheduleTask(taskName);
        }
    };

    const expandButton = document.createElement("button");
    expandButton.classList.add("expand-btn");
    expandButton.innerHTML = '<i class="fas fa-chevron-down"></i>'; // Default chevron down
    expandButton.onclick = () => toggleSubTasks(expandButton, subTaskContainer);

    const subTaskContainer = document.createElement("div");
    subTaskContainer.classList.add("subTaskContainer", "hidden");
    subTaskContainer.innerHTML = "<p>No scheduled tasks</p>";

    taskItem.appendChild(statusSpan);
    taskItem.appendChild(label);
    taskItem.appendChild(intervalInputContainer);
    taskItem.appendChild(countdownSpan);
    taskItem.appendChild(actionButton);
    taskItem.appendChild(expandButton);
    taskItem.appendChild(subTaskContainer);

    return taskItem;
}

function updateTaskElement(taskName, taskData) {
    const taskItem = document.querySelector(`.taskScheduleItem[data-task-name="${taskName}"]`);
    if (!taskItem) {
        console.error(`Task element for ${taskName} not found.`);
        return;
    }

    const statusSpan = taskItem.querySelector(".status");
    statusSpan.innerText = taskData.status ? "Active" : "Disabled";
    statusSpan.classList.toggle("active", taskData.status);
    
    const countdownSpan = taskItem.querySelector(".countdown");
    taskData.status ? countdownToDate(taskName, taskData, countdownSpan) : countdownSpan.innerText = "Not scheduled";
    // countdownSpan.innerText = taskData.status ? taskData.next_run : "Not scheduled";

    const intervalValue = taskItem.querySelector(".intervalValue");
    const intervalUnit = taskItem.querySelector("#intervalUnit");
    if (intervalValue) {
        intervalValue.disabled = taskData.status;
        intervalUnit.disabled = taskData.status;
    }

    const actionButton = taskItem.querySelector(".taskActionBtn");
    actionButton.innerText = taskData.status ? "Deactivate" : "Activate";
    actionButton.classList.toggle("deactivate", taskData.status);
    actionButton.onclick = () => {
        if (taskData.status) {
            deleteScheduledTask(taskName);
        } else {
            scheduleTask(taskName);
        }
    };
}

function createSubTaskElement(subTaskName, subTaskData, subTaskContainer) {
    subTaskContainer.innerHTML = "";
    const subTaskItem = document.createElement("div");
    subTaskItem.classList.add("subTaskItem");
    subTaskItem.setAttribute("data-sub-task-name", subTaskName);

    // Sub-task name label
    const label = document.createElement("label");
    label.innerText = subTaskName.replace(/^email_/, "");

    // Countdown timer span
    const countdownSpan = document.createElement("span");
    countdownSpan.classList.add("countdown");
    countdownToDate(subTaskName, subTaskData, countdownSpan);

    // Delete button
    const deleteButton = document.createElement("button");
    deleteButton.classList.add("delete-btn");
    deleteButton.innerHTML = '<i class="fas fa-trash-alt"></i>'; // FontAwesome trash icon
    deleteButton.onclick = () => deleteScheduledTask(subTaskData.id);

    // Append elements
    subTaskItem.appendChild(label);
    subTaskItem.appendChild(countdownSpan);
    subTaskItem.appendChild(deleteButton);

    return subTaskItem;
}

function deleteSubTaskElement(subTaskName, subTaskContainer) {
    const elementToRemove = subTaskContainer.querySelector(`[data-sub-task-name="${subTaskName}"]`);
    
    if (elementToRemove) {
        elementToRemove.remove();
    }
    
    if (subTaskContainer.children.length === 0) {
        subTaskContainer.innerHTML = "<p>No scheduled tasks</p>";
    }
}

function countdownToDate(name, data, element) {
    let targetDate = new Date(data.next_run).getTime();

    const unit = data.interval_unit == "days" ? 24 * 60 * 60 * 1000 : 
                 data.interval_unit == "hours" ? 60 * 60 * 1000 : 
                 data.interval_unit == "minutes" ? 60 * 1000 : 
                 1000;

    const countdownInterval = setInterval(function() {
        const now = new Date().getTime();
        const distance = targetDate - now;

        if (distance <= 0) {
            targetDate = (now + data.interval_value * unit);
        } else {
            const days = Math.floor(distance / (1000 * 60 * 60 * 24));
            const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((distance % (1000 * 60)) / 1000);
            
            const countdownText = `${days}d ${padZero(hours)}:${padZero(minutes)}:${padZero(seconds)}`;
            element.innerText = countdownText;
        }
    }, 1000);
    taskIntervals[name] = countdownInterval;

    function padZero(num) {
        return num < 10 ? "0" + num : num;
    }
}