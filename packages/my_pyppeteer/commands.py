from cleo import Command
from packages.core.utils.app_loop import AppLoop
from packages.my_pyppeteer.ctrls import MyPyppeteer


class AllCommands:

    class OpenPyppeteerBrowser(Command):
        """
        Open Pyppeteer Browser --headless=0

        pyppeteer:open_browser
        {--args= : nothing extra by default}
        {--headless= : headless =0 by default}
        {--profile-name= : profile-name}
        """

        def handle(self):

            headless = bool(self.option('headless'))
            profile_name = self.option('profile-name')
            args = self.option('args')
            if args:
                args = args.split(',')
            else:
                args = []
            AppLoop().get_loop().run_until_complete(MyPyppeteer().open_browser(headless=headless, profile_name=profile_name, args=args))

    class CommandCountPages(Command):
        """
        Run count pages

        pyppeteer:count_pages
        {--profile-name= : profile-name}
        """

        def handle(self):
            profile_name = self.option('profile-name')
            AppLoop().get_loop().run_until_complete(MyPyppeteer(profile_name).count_pages())

    class CommandProfileName(Command):
        """
        Run rotate_pages

        pyppeteer:rotate_pages
        {--profile-name= : profile-name}
        """

        def handle(self):
            profile_name = self.option('profile-name')
            AppLoop().get_loop().run_until_complete(MyPyppeteer(profile_name).start_rotate_pages())