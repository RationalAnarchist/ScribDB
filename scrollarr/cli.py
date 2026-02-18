import argparse
import sys
from .story_manager import StoryManager
from .logger import setup_logging

def add_story_command(url):
    print(f"Adding story from {url}...")
    manager = StoryManager()
    try:
        story_id = manager.add_story(url)
        print(f"Story added with ID: {story_id}")

        print("Downloading missing chapters...")
        manager.download_missing_chapters(story_id)
        print("Download complete.")

    except Exception as e:
        print(f"Error adding story: {e}")
        sys.exit(1)

def list_stories_command():
    manager = StoryManager()
    try:
        stories = manager.list_stories()
        if not stories:
            print("No stories found.")
            return

        print(f"{'ID':<5} {'Title':<40} {'Author':<20} {'Progress':<10}")
        print("-" * 80)
        for story in stories:
            title = story['title']
            if len(title) > 37:
                title = title[:37] + "..."

            author = story['author']
            if len(author) > 17:
                author = author[:17] + "..."

            progress = f"{story['downloaded']}/{story['total']}"
            print(f"{story['id']:<5} {title:<40} {author:<20} {progress:<10}")

    except Exception as e:
        print(f"Error listing stories: {e}")
        sys.exit(1)

def compile_story_command(story_id):
    print(f"Compiling story ID: {story_id}...")
    manager = StoryManager()
    try:
        output_path = manager.compile_story(int(story_id))
        print(f"Successfully compiled ebook to: {output_path}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Scrollarr CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add command
    parser_add = subparsers.add_parser("add", help="Add and monitor a story")
    parser_add.add_argument("url", help="URL of the story to add")

    # List command
    parser_list = subparsers.add_parser("list", help="List all stories and progress")

    # Compile command
    parser_compile = subparsers.add_parser("compile", help="Compile a story to EPUB")
    parser_compile.add_argument("story_id", help="ID of the story to compile")

    args = parser.parse_args()

    if args.command == "add":
        add_story_command(args.url)
    elif args.command == "list":
        list_stories_command()
    elif args.command == "compile":
        compile_story_command(args.story_id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
