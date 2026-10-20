from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"placeholder": "Username or email", "autofocus": True, "autocomplete": "username"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Password", "autocomplete": "current-password"}))

    def clean(self):
        # allow logging in with the e-mail address as well
        username = self.cleaned_data.get("username", "")
        if "@" in username:
            match = User.objects.filter(email__iexact=username).first()
            if match:
                self.cleaned_data["username"] = match.username
        return super().clean()


class RegisterForm(UserCreationForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"placeholder": "you@example.com", "autocomplete": "email"}))

    class Meta:
        model = User
        fields = ("username", "email")
        widgets = {"username": forms.TextInput(attrs={"placeholder": "Choose a username", "autofocus": True, "autocomplete": "username"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update({"placeholder": "Password (8+ characters)", "autocomplete": "new-password"})
        self.fields["password2"].widget.attrs.update({"placeholder": "Repeat password", "autocomplete": "new-password"})

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this e-mail already exists.")
        return email
