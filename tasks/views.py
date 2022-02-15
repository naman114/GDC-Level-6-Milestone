from re import template
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from tasks.models import Task

from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.forms import ModelForm
from django.core.exceptions import ValidationError
from django.views.generic.detail import DetailView
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin


class AuthorizedTaskManager(LoginRequiredMixin):
    def get_queryset(self):
        tasks = Task.objects.filter(
            deleted=False, completed=False, user=self.request.user
        )
        return tasks


################################ Pending tasks ##########################################
class GenericTaskView(LoginRequiredMixin, ListView):
    queryset = Task.objects.filter(deleted=False, completed=False)
    template_name = "pending_tasks.html"
    context_object_name = "tasks"
    paginate_by = 5

    def get_queryset(self):
        search_term = self.request.GET.get("search")
        tasks = Task.objects.filter(
            deleted=False, completed=False, user=self.request.user
        ).order_by("priority")

        if search_term:
            tasks = tasks.filter(title__icontains=search_term)

        return tasks


################################ Completed tasks ##########################################
class GenericCompletedTaskView(LoginRequiredMixin, ListView):
    queryset = Task.objects.filter(completed=True)
    template_name = "completed_tasks.html"
    context_object_name = "tasks"
    paginate_by = 5

    def get_queryset(self):
        search_term = self.request.GET.get("search")
        tasks = Task.objects.filter(completed=True, user=self.request.user).order_by(
            "priority"
        )

        if search_term:
            tasks = tasks.filter(title__icontains=search_term)

        return tasks


################################ All tasks ##########################################
class GenericAllTaskView(LoginRequiredMixin, ListView):
    queryset = Task.objects.filter(deleted=False)
    template_name = "all_tasks.html"
    context_object_name = "tasks"

    def get_context_data(self, **kwargs):
        context = super(GenericAllTaskView, self).get_context_data(**kwargs)
        context["active_tasks"] = Task.objects.filter(
            deleted=False, completed=False, user=self.request.user
        ).order_by("priority")
        context["completed_tasks"] = Task.objects.filter(
            completed=True, user=self.request.user
        ).order_by("priority")
        search_term = self.request.GET.get("search")
        if search_term:
            context["active_tasks"] = context["active_tasks"].filter(
                title__icontains=search_term
            )
            context["completed_tasks"] = context["completed_tasks"].filter(
                title__icontains=search_term
            )
        return context


################################ Task Detail View ##########################################
class GenericTaskDetailView(AuthorizedTaskManager, DetailView):
    model = Task
    template_name = "task_detail.html"


################################ Add a task ##########################################
class TaskCreateForm(ModelForm):
    def clean_title(self):
        # cleaned_data is django's representation of all data collected from the form
        title = self.cleaned_data["title"]
        if len(title) < 10:
            raise ValidationError("Error: Length must be 10 characters")
        return title.upper()

    class Meta:
        model = Task
        fields = ("title", "description", "priority", "completed")


class GenericTaskCreateView(LoginRequiredMixin, CreateView):
    form_class = TaskCreateForm
    template_name = "task_create.html"
    success_url = "/tasks"

    def form_valid(self, form):
        self.object = form.save()
        self.object.user = self.request.user

        tasks_matching_priority = Task.objects.filter(
            priority=self.object.priority,
            user=self.request.user,
            deleted=False,
            completed=False,
        )
        if tasks_matching_priority.exists():
            pending_tasks = Task.objects.filter(
                user=self.request.user, completed=False, deleted=False
            )
            priority_pk_dict = {}
            for task in pending_tasks:
                priority_pk_dict[task.priority] = task.pk

            for key in sorted(priority_pk_dict.keys(), reverse=True):
                taskToUpdate = Task.objects.get(pk=priority_pk_dict[key])
                taskToUpdate.priority += 1
                taskToUpdate.save()
                if key == self.object.priority:
                    break

        self.object.save()
        return HttpResponseRedirect(self.get_success_url())


################################ Update a task ##########################################
class GenericTaskUpdateView(AuthorizedTaskManager, UpdateView):
    model = Task
    form_class = TaskCreateForm
    template_name = "task_update.html"
    success_url = "/tasks"

    def form_valid(self, form):
        existing_priority = Task.objects.get(pk=self.object.pk).priority
        pending_tasks = Task.objects.filter(
            user=self.request.user, completed=False, deleted=False
        )

        tasks_matching_priority = Task.objects.filter(
            priority=self.object.priority,
            user=self.request.user,
            deleted=False,
            completed=False,
        )

        if tasks_matching_priority.exists():
            priority_pk_list = []
            for task in pending_tasks:
                priority_pk_list.append([task.priority, task.pk])

            target_priority = tasks_matching_priority.first().priority

            if existing_priority > target_priority:
                priority_pk_list.sort(reverse=True)
                flag = False
                for item in priority_pk_list:
                    if flag == False:
                        if item[0] == existing_priority:
                            flag = True
                    else:
                        taskToUpdate = Task.objects.get(pk=item[1])
                        taskToUpdate.priority += 1
                        taskToUpdate.save()
                        if item[0] == target_priority:
                            break

            else:
                priority_pk_list.sort()
                flag = False
                for item in priority_pk_list:
                    if flag == False:
                        if item[0] == existing_priority:
                            flag = True
                    else:
                        taskToUpdate = Task.objects.get(pk=item[1])
                        taskToUpdate.priority -= 1
                        taskToUpdate.save()
                        if item[0] == target_priority:
                            break

        self.object = form.save()
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())


################################ Delete a task ##########################################
class GenericTaskDeleteView(AuthorizedTaskManager, DeleteView):
    model = Task
    template_name = "task_delete.html"
    success_url = "/tasks"


################################ Mark task as complete ##########################################
class GenericMarkTaskAsCompleteView(AuthorizedTaskManager, UpdateView):
    model = Task
    fields = []
    template_name = "task_complete.html"
    success_url = "/tasks"

    def form_valid(self, form):
        self.object = form.save()
        self.object.completed = True
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())


################################ Session Storage ##########################################
def session_storage_view(request):
    print(
        request.session
    )  # <django.contrib.sessions.backends.db.SessionStore object at 0x7f8fa8126d90> (It is a dict)

    # Get the total views from the session
    total_views = request.session.get("total_views", 0)
    # Store the value back in the session
    request.session["total_views"] = total_views + 1
    # Render it back to us
    return HttpResponse(
        f"Total views is {total_views} and the user is {request.user} and are they authenticated? {request.user.is_authenticated}"
    )


################################ User Sign Up ##########################################
class UserCreateView(CreateView):
    form_class = UserCreationForm
    template_name = "user_create.html"
    success_url = "/user/login"


class UserLoginView(LoginView):
    template_name = "user_login.html"
