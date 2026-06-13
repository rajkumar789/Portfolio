import os
import requests
import re
from django.core.management.base import BaseCommand
from django.db.models.signals import post_save
from django.utils.text import slugify
from portfolio.models import Project, Article
from portfolio.models import notify_subscribers_new_project, send_new_article_notification

class Command(BaseCommand):
    help = 'Clears existing projects and articles, and fetches new projects from GitHub'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='rajkumar789',
            help='GitHub username to fetch repositories from'
        )
        parser.add_argument(
            '--include-forks',
            action='store_true',
            help='Include forked repositories'
        )

    def handle(self, *args, **options):
        username = options['username']
        include_forks = options['include_forks']

        # Disconnect signals to prevent slow SMTP connections/emails during bulk sync
        post_save.disconnect(notify_subscribers_new_project, sender=Project)
        post_save.disconnect(send_new_article_notification, sender=Article)

        self.stdout.write(self.style.WARNING("Clearing all projects and articles from the database..."))
        Project.objects.all().delete()
        Article.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("Database cleared successfully."))

        self.stdout.write(f"Fetching public repositories for user '{username}' from GitHub...")
        url = f"https://api.github.com/users/{username}/repos?per_page=100"
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            repos = response.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to fetch repositories from GitHub: {e}"))
            return

        if not isinstance(repos, list):
            self.stdout.write(self.style.ERROR(f"Unexpected response from GitHub: {repos}"))
            return

        imported_count = 0
        for repo in repos:
            if repo.get('fork') and not include_forks:
                continue

            repo_name = repo.get('name', '')
            repo_desc = repo.get('description', '') or ''
            repo_url = repo.get('html_url', '')
            repo_homepage = repo.get('homepage') or ''
            repo_lang = repo.get('language') or ''

            # Generate a nice title
            # Replace dashes/underscores with space, titlecase
            clean_title = repo_name.replace('-', ' ').replace('_', ' ')
            # Specific cleanups
            clean_title = re.sub(r'(?i)powerbi', 'Power BI', clean_title)
            clean_title = re.sub(r'(?i)boot.dev', 'Boot.dev', clean_title)
            clean_title = clean_title.title()

            # Rule-based technology extraction
            tech_keywords = {
                'django': 'Django',
                'flask': 'Flask',
                'pandas': 'Pandas',
                'numpy': 'NumPy',
                'scikit-learn': 'Scikit-learn',
                'react': 'React',
                'vue': 'Vue',
                'angular': 'Angular',
                'jquery': 'jQuery',
                'power bi': 'Power BI',
                'tableau': 'Tableau',
                'excel': 'Excel',
                'machine learning': 'Machine Learning',
                'deep learning': 'Deep Learning',
                'python': 'Python',
                'javascript': 'JavaScript',
                'typescript': 'TypeScript',
                'html': 'HTML',
                'css': 'CSS',
                'mysql': 'MySQL',
                'postgresql': 'PostgreSQL',
                'mongodb': 'MongoDB',
                'sql': 'SQL',
                'java': 'Java',
                'c++': 'C++',
                'c#': 'C#',
                'ruby': 'Ruby',
                'php': 'PHP',
                'go': 'Go',
                'rust': 'Rust',
            }

            tech_list = []
            if repo_lang:
                tech_list.append(repo_lang)

            text_to_scan = f"{repo_name} {repo_desc}".lower()
            for key, val in tech_keywords.items():
                if key in text_to_scan:
                    if val not in tech_list:
                        tech_list.append(val)

            # limit technologies to top 5
            technologies = ", ".join(tech_list[:5])
            if not technologies:
                technologies = "Software Development"

            # Fallback description
            description = repo_desc if repo_desc else f"GitHub repository containing source code and resources for {clean_title}."

            # Fetch README.md raw content
            full_content = ""
            for branch in ['main', 'master']:
                readme_url = f"https://raw.githubusercontent.com/{username}/{repo_name}/{branch}/README.md"
                try:
                    readme_resp = requests.get(readme_url, timeout=5)
                    if readme_resp.status_code == 200:
                        full_content = readme_resp.text
                        break
                except Exception:
                    pass

            if not full_content:
                # Default description block if no README is found
                full_content = f"""# {clean_title}

{description}

## Technologies Used
- {technologies}

## Repository Link
Access the full code repository on GitHub: [{clean_title}]({repo_url})
"""

            # Ensure slug is unique
            slug = slugify(clean_title)
            original_slug = slug
            counter = 1
            while Project.objects.filter(slug=slug).exists():
                slug = f"{original_slug}-{counter}"
                counter += 1

            # Save the Project
            try:
                project = Project(
                    title=clean_title,
                    slug=slug,
                    description=description,
                    technologies=technologies,
                    github_link=repo_url,
                    live_link=repo_homepage,
                    full_content=full_content
                )
                project.save()
                imported_count += 1
                self.stdout.write(self.style.SUCCESS(f"Imported project: {clean_title}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to save project '{clean_title}': {e}"))

        self.stdout.write(self.style.SUCCESS(f"Successfully imported {imported_count} projects from GitHub."))
