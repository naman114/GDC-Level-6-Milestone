from itertools import chain
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.safestring import mark_safe
from tasks.models import Task

from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.forms import ModelForm
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.views.generic.detail import DetailView
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction

class AuthorizedTaskManager(LoginRequiredMixin):
    def get_queryset(self):
        tasks = Task.objects.filter(
            deleted=False, completed=False, user=self.request.user
        )
        return tasks


class TaskProgressManager:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["completed_tasks_count"] = Task.objects.filter(
            completed=True, user=self.request.user
        ).count()
        context["total_tasks_count"] = (
            context["completed_tasks_count"]
            + Task.objects.filter(
                deleted=False, completed=False, user=self.request.user
            ).count()
        )
        return context


def handlePriorityCascading(new_priority, user):
    with transaction.atomic():
        # Fetching all pending tasks of the user
        pending_tasks = Task.objects.filter(user=user, completed=False, deleted=False).select_for_update()

        tasksToUpdate = []

        while True:
            try:
                taskToUpdate = pending_tasks.get(priority=new_priority)
                taskToUpdate.priority += 1
                tasksToUpdate.append(taskToUpdate)
                new_priority += 1

            except ObjectDoesNotExist:
                break

        Task.objects.bulk_update(tasksToUpdate, ["priority"])


################################ Pending tasks ##########################################
class GenericTaskView(LoginRequiredMixin, TaskProgressManager, ListView):
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
class GenericCompletedTaskView(LoginRequiredMixin, TaskProgressManager, ListView):
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
class GenericAllTaskView(LoginRequiredMixin, TaskProgressManager, ListView):
    queryset = Task.objects.filter(deleted=False)
    template_name = "all_tasks.html"
    context_object_name = "tasks"
    paginate_by = 5

    def get_queryset(self):
        search_term = self.request.GET.get("search")
        active_tasks = Task.objects.filter(
            deleted=False, completed=False, user=self.request.user
        ).order_by("priority")
        completed_tasks = Task.objects.filter(
            completed=True, user=self.request.user
        ).order_by("priority")

        if search_term:
            active_tasks = active_tasks.filter(title__icontains=search_term)
            completed_tasks = completed_tasks.filter(title__icontains=search_term)

        tasks = list(chain(active_tasks, completed_tasks))

        return tasks


################################ Task Detail View ##########################################
class GenericTaskDetailView(DetailView):
    model = Task
    template_name = "task_detail.html"

    # The details of both completed and pending tasks can be viewed
    def get_queryset(self):
        tasks = Task.objects.filter(deleted=False, user=self.request.user)
        return tasks


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].widget.attrs[
            "class"
        ] = "mb-7 block w-full px-3 py-2 bg-gray-100 text-gray-900 rounded-lg"
        self.fields["description"].widget.attrs[
            "class"
        ] = "mb-7 block w-full px-3 py-2 bg-gray-100 text-gray-900 rounded-lg"
        self.fields["description"].widget.attrs["cols"] = "30"
        self.fields["description"].widget.attrs["rows"] = "5"
        self.fields["priority"].widget.attrs[
            "class"
        ] = "mb-7 block w-full px-3 py-2 bg-gray-100 text-gray-900 rounded-lg"
        self.fields["completed"].widget.attrs["class"] = "ml-2"


class GenericTaskCreateView(LoginRequiredMixin, CreateView):
    form_class = TaskCreateForm
    template_name = "task_create.html"
    success_url = "/tasks"

    def form_valid(self, form):
        new_priority = form.cleaned_data["priority"]

        handlePriorityCascading(new_priority, self.request.user)

        self.object = form.save()
        self.object.user = self.request.user
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())


################################ Update a task ##########################################
class GenericTaskUpdateView(AuthorizedTaskManager, UpdateView):
    model = Task
    form_class = TaskCreateForm
    template_name = "task_update.html"
    success_url = "/tasks"

    def form_valid(self, form):
        existing_priority = Task.objects.get(id=self.object.id).priority
        new_priority = form.cleaned_data["priority"]

        if existing_priority != new_priority:
            handlePriorityCascading(new_priority, self.request.user)

        self.object = form.save()
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


class UserSignupForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs[
            "class"
        ] = "mb-7 block w-full px-3 py-2 bg-gray-100 text-gray-900 rounded-lg"
        self.fields["username"].help_text = mark_safe(
            '<p class="text-sm -mt-10 mb-10"> Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.</p>'
        )
        self.fields["password1"].widget.attrs[
            "class"
        ] = "mb-7 block w-full px-3 py-2 bg-gray-100 text-gray-900 rounded-lg"
        self.fields["password1"].help_text = mark_safe(
            "<ul class='-mt-10 mb-10'><li class='text-sm'>Your password can't be too similar to your other personal information.</li><li class='text-sm'>Your password must contain at least 8 characters.</li><li class='text-sm'>Your password can't be a commonly used password.</li><li class='text-sm'>Your password can't be entirely numeric.</li></ul>"
        )
        self.fields["password2"].widget.attrs[
            "class"
        ] = "mb-7 block w-full px-3 py-2 bg-gray-100 text-gray-900 rounded-lg"
        self.fields["password2"].help_text = mark_safe(
            "<p class='text-sm -mt-10 mb-10'>Enter the same password as before, for verification.</p>"
        )
        self.error_css_class = "text-sm"


class UserCreateView(CreateView):
    form_class = UserSignupForm
    template_name = "user_create.html"
    success_url = "/user/login"


class UserLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs[
            "class"
        ] = "mb-7 block w-full px-3 py-2 bg-gray-100 text-gray-900 rounded-lg"
        self.fields["password"].widget.attrs[
            "class"
        ] = "mb-7 block w-full px-3 py-2 bg-gray-100 text-gray-900 rounded-lg"


class UserLoginView(LoginView):
    template_name = "user_login.html"
    authentication_form = UserLoginForm
