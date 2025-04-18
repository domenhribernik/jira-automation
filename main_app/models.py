from django.db import models

class ScheduledTask(models.Model):
    status = models.IntegerField()
    task_id = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=30, unique=True)
    interval_value = models.IntegerField()
    interval_unit = models.CharField(max_length=10, choices=[('seconds', 'Seconds'), ('minutes', 'Minutes'), ('hours', 'Hours'), ('days', 'Days')])
    next_run = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name