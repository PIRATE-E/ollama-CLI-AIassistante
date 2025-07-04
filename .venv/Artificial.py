import ollama
import os
import psutil
import subprocess
import sys
import time
# from history import histoty_ai
from login import LoginAI
from rich import pretty, traceback, console, print
from rich.padding import Padding
from rich.panel import Panel
from rich.prompt import Prompt
from history import chat_history


class Artificial_AI():

    @staticmethod
    def timeR(fun):
        def wrapper(*args, **kwargs):
            st = time.perf_counter()
            result = fun(*args, **kwargs)
            en = time.perf_counter()
            print(f"\ttime taken [bold red]{str(fun.__name__)}:-[/bold red][blue underline]{en - st}")
            return result

        return wrapper

    @timeR
    def __init__(self):

        self.my_console = console.Console()
        pretty.install()
        traceback.install(show_locals=True)

        self.ollama_server = None
        self.client = None
        self.messages_ollama = []  # length must be 2 one is system-prompt second is user-prompt

        self.temp = 0.5
        self.top_p = 0.5
        self.max_tockens = 200
        self.alive = '-1'

        self._cleaned_up_flag = False

        self.start_time = 0

        self.tocken_generated = 0

        self.ollama_server_pid_ram = 0

        self.history_dict = {}  # some thing like
        """
        {
        1: ['prompt', 'response'],
        2: ['prompt2', 'response2']
        }
        """
        self.prompt_response_list = []  # if user decided to add all chat before exit() [['prompt1','response1'],['prompt2','response2']]
        self.last_prompt = None


        self.chat_history = chat_history()
        self.chat_history.my_console = self.my_console
        self.chat_history.prompt_response_list = self.prompt_response_list
        self.chat_history.history_dict = self.history_dict

        self.connection()
        pass

    def cpu_utilization(self, utilization):
        # get system information <cores/thread(logical cores)>
        cores = psutil.cpu_count(logical=False)  # this is for core (logical+True=threads)
        threads = psutil.cpu_count(logical=True)

        assert self.ollama_server is not None, "server has been not initialized yet"  # is this comes join thread_connection
        ollama_server_pid = psutil.Process(self.ollama_server.pid)
        if utilization:
            ollama_server_pid.nice(psutil.REALTIME_PRIORITY_CLASS)  # set as realtime maxed high priority process

            ollama_server_pid.cpu_affinity(
                list(range(cores)))  # bind with no of cores/threads   max thread are fastest
            # server_process.ionice(ioclass=psutil.IOPRIO_CLASS_RT)  # realtime max i/o priority

            self.my_console.print(f"\tcurrent process "
                                  f"[yellow][bold o][u]STATUS[/bold o][/u][/yellow] is :- "
                                  f"[green blink]{ollama_server_pid.nice()}[/green blink]", ":warning:")
        pass

    def get_tocken(self, time_tacken):
        # we can use no of words / time taken  = tocken generated
        if time_tacken == 0:
            return 0
        else:
            return self.tocken_generated / time_tacken
        # average of tockens
        pass

    def connection(self):
        try:
            # this for not printing the log of webserver of ollama server
            self.ollama_server = subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL,
                                                  stderr=subprocess.DEVNULL)

            # print the log of webserver
            # self.ollama_server = subprocess.Popen(["ollama", "serve"])

            self.cpu_utilization(True)

            self.client = ollama.Client()

        except Exception as e:
            print(e)
        pass

    def set_system_txt(self, content):
        self.messages_ollama.append({'role': 'system', 'content': content})

    def set_user_message(self, query, autoRun=False):
        """
        actually i have to make message_ollama_list upto length of 2 because after appending the user prompt it
        start the explaining about previous user prompt
        :param query:
        :param autoRun:
        :return:
        """
        if len(self.messages_ollama) >= 2: self.messages_ollama.pop()
        self.messages_ollama.append({'role': 'user', 'content': query})

        if autoRun:
            self.run_connect()
            #         run the connect get output from the ollama deep seek

    def options_change(self, temperature: float, top_p: float, max_tocken: int, alive: str):
        self.temp = temperature
        self.top_p = top_p
        self.max_tockens = max_tocken
        self.alive = alive

    def run_connect(self):
        opt = {
            "temperature": self.temp,
            "keep_alive": self.alive,
            "top_p": self.top_p,
            "num_predict": self.max_tockens
        }
        self.start_time = time.perf_counter()
        try:
            response_str = ""
            response = self.client.chat(model='deepseek-r1:7b', messages=self.messages_ollama, options=opt, stream=True)
            for chunk in response:
                print(chunk['message']['content'], end='', flush=True)
                response_str += chunk['message']['content']
                self.tocken_generated += 1

            # append the p_r_list for dump
            self.prompt_response_list.append([self.last_prompt, response_str])

            self.ollama_server_pid_ram = psutil.Process(self.ollama_server.pid).memory_info().rss
            parent = psutil.Process(self.ollama_server.pid)
            for child in parent.children(recursive=True):
                if child.is_running():
                    self.ollama_server_pid_ram += child.memory_info().rss

        except (KeyboardInterrupt, TypeError, psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self.my_console.print(f"\n[bold red]error[/bold red] while streaming \t{e}")

    pass

    def response_information(self):
        """
        this method is used to display information ram, tps, time of every response generated by ollama
        :return:
        """
        end_time = time.perf_counter()
        total_time_tacken = end_time - self.start_time

        python_script_pid_ram = psutil.Process(os.getpid()).memory_info().rss

        total_ram = self.ollama_server_pid_ram + python_script_pid_ram

        self.my_console.print("\n[bold strike red on white]response over")

        self.my_console.print(Panel.fit(f"[bold] time taken to generate response:- {total_time_tacken:.4f}\n"
                                        f"ram consumed by this is :- {total_ram / (1024 ** 3):.2f} GB\n"
                                        f"tockens per second we got {self.get_tocken(total_time_tacken):.2f}"
                                        , subtitle="information", subtitle_align='center', title="system and response",
                                        title_align='center', safe_box=False,
                                        padding=(1, 10, 1, 10), highlight=True, style='red'), justify='center')

    def log_out(self):

        self.ollama_server.terminate()
        self.ollama_server.wait()

        if os.name == "nt":  # windows
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.name() == "ollama_llama_server.exe":
                    try:
                        result = subprocess.run(["taskkill", "/F", "/IM", "ollama_llama_server.exe"], check=True,
                                                capture_output=True)

                        # time.sleep(5)
                        print(result.stdout, result.stderr)
                    except subprocess.CalledProcessError as e:
                        if e.returncode == 128:
                            print("server is already killed")
                        print(e)

        else:  # mac/linux
            os.system("pkill -f ollama")

        self.my_console.rule("[blink green]AI assistance has been close", style='red', align='center')

        pass

    def cleanUp(self):
        if self._cleaned_up_flag:
            pass
        else:
            self.log_out()
            self._cleaned_up_flag = True
        pass

    def handel_intrupt(self, signum, frame):
        print(f"\n🛑 Received signal {signum}. Exiting gracefully...")
        self.cleanUp()
        exit()
        pass

    def manageLogin(self):
        login_obj = LoginAI()
        login_obj.create_table()
        if Prompt.ask("are you willing to login", choices=["yes", "no"], default="no") == 'yes':
            self.my_console.print("[bold green]user is trying to login[/bold green]", justify='center')
            username = Prompt.ask("\tenter your username")
            password = Prompt.ask("\tenter your password", password=True)
            if login_obj.login(username, password):
                self.my_console.print(f"[bold green]logged in successfully[/bold green] [red blink]{login_obj.get_username()}[/red blink]")
            else:
                self.my_console.print("[bold red]login failed[/bold red]")
                if Prompt.ask("try again", choices=["yes", "no"], default="no") == "yes":
                    self.manageLogin()
                else:sys.exit()
        else:
            self.my_console.print("[bold green]user is trying to signup[/bold green]", justify='center')
            username = Prompt.ask("\tenter your username")
            password = Prompt.ask("\tenter your password", password=True)
            if login_obj.create_account(username, password):
                self.my_console.print(f"[bold green]account created successfully[/bold green] [red blink]{login_obj.get_username()}[/red blink]")
            else:
                self.my_console.print("[bold red]account creation failed[/bold red]")
                if login_obj.userpresent:
                    self.my_console.print("[bold red]account already present[/bold red]")
                if Prompt.ask("try again", choices=["yes", "no"], default="no") == "yes":
                    self.manageLogin()
                sys.exit()

    def welcome(self):
        # here i have to tell that this is chat bot plz enter your desired settings and then after setting up
        """
        like :-
        "temperature": self.temp,
            "keep_alive": self.alive,
            "top_p": self.top_p,
            "num_predict": self.max_tockens
        :return:
        """
        # you can chat with this bot
        pad = Padding("[blink red] welcome to smart AI", (1, 1, 1, 10))
        self.my_console.rule("[blink red] welcome to smart AI",
                             style="green", align='center')
        self.manageLogin()

        self.my_console.rule("please set up your AI assistance personality", style="bold ")

        choice_get = [
            ["random", "strict", "entermediate"],
            ["short", "long", "extreme"],
            ["yes", "no"]
        ]

        choice_set = [
            [1, 0, 0.5],
            [200, 1500, 2000],
            [True, False]
        ]

        temprature = Prompt.ask("Enter the desired output type", choices=choice_get[0], default="strict")

        output_length = Prompt.ask("Enter the preferred length of output", choices=choice_get[1], default="short")

        # here i have to show the history-previous prompt of the user and give option to add this history of not

        # new
        self.chat_history.load_history()
        self.chat_history.show_history()

        self.temp = choice_set[0][choice_get[0].index(temprature)]
        self.max_tockens = choice_set[1][choice_get[1].index(output_length)]
        # no feature related history
        # now set it to options
        pass

    def handle_running(self):
        # maintaining chatting loop till user wants to exit
        prompt = Prompt.ask("enter your query :- {[bold yellow]for exit type exit(0)[/bold yellow]}",
                            default="exit(0)",
                            show_default=False)
        panel_prompt = Panel.fit(f"[bold yellow]{prompt}", style='red')
        print(panel_prompt, ":backhand_index_pointing_down:")
        if prompt == "exit(0)":
            if self.last_prompt is None:  # we will check did user ask something before exit
                sys.exit()
            else:
                self.chat_history.dump_history()
                # self.chat_history.dump_history(self.prompt_response_list)
                sys.exit()
        else:
            while (True):
                self.last_prompt = prompt
                self.set_user_message(prompt, True)
                self.response_information()

                self.handle_running()
        pass