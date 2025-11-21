'''
    Date  : 2019/09
    Author: Doem
    E-mail: aa0917954358@gmail.com
    
    GUI Version with tkinter interface
'''

import os
import sys
import cv2
import time
import requests
import numpy as np
import tkinter as tk
from tkinter import scrolledtext, messagebox
from threading import Thread
from bs4 import BeautifulSoup
from keras.models import load_model
import tensorflow as tf

# 修復 PyInstaller 打包後 sys.stdout 和 sys.stderr 為 None 的問題
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

# 獲取資源檔案的正確路徑（支援 PyInstaller 打包）
def resource_path(relative_path):
    """取得資源檔案的絕對路徑，支援開發環境和 PyInstaller 打包後的環境"""
    try:
        # PyInstaller 創建的臨時資料夾路徑
        base_path = sys._MEIPASS
    except AttributeError:
        # 開發環境中使用當前目錄
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class CourseBot:
    def __init__(self, account, password, log_callback=None):
        self.account = account
        self.password = password
        self.coursesDB = {}
        self.log_callback = log_callback
        
        # captcha.png 存放在當前工作目錄（用戶執行 exe 的地方，有寫入權限）
        self.captcha_path = os.path.join(os.getcwd(), 'captcha.png')

        # for keras - 直接載入模型但不編譯（從打包資源中讀取）
        model_path = resource_path('model.h5')
        try:
            self.model = load_model(model_path)
        except ValueError as e:
            if 'lr' in str(e):
                # 直接載入模型但跳過編譯
                self.model = load_model(model_path, compile=False)
                # 手動重新編譯
                self.model.compile(
                    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                    loss='categorical_crossentropy',
                    metrics=['accuracy']
                )
            else:
                raise e
        
        self.n_classes = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'

        # for requests
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36'

        self.loginUrl = 'https://isdna1.yzu.edu.tw/CnStdSel/Index.aspx'
        self.captchaUrl = 'https://isdna1.yzu.edu.tw/CnStdSel/SelRandomImage.aspx'
        self.courseListUrl = 'https://isdna1.yzu.edu.tw/CnStdSel/SelCurr/CosList.aspx'
        self.courseSelectUrl = 'https://isdna1.yzu.edu.tw/CnStdSel/SelCurr/CurrMainTrans.aspx?mSelType=SelCos&mUrl='

        self.loginPayLoad = {
            '__VIEWSTATE': '',
            '__VIEWSTATEGENERATOR': '',
            '__EVENTVALIDATION': '',
            'DPL_SelCosType': '',
            'Txt_User': self.account,
            'Txt_Password': self.password,
            'Txt_CheckCode': '',
            'btnOK': '確定'
        }

        self.selectPayLoad = {}

    def predict(self, img):
        # 使用 verbose=0 避免在 GUI 模式下輸出進度條
        prediction = self.model.predict(np.array([img]), verbose=0)

        predicStr = ""
        for pred in prediction:
            predicStr += self.n_classes[np.argmax(pred[0])]
        return predicStr

    def captchaOCR(self):
        captchaImg = cv2.imread(self.captcha_path) / 255.0
        return self.predict(captchaImg)

    # login into system and get session
    def login(self):
        
        while True:
            # clear Session object
            self.session.cookies.clear()

            # download and recognize captch
            with self.session.get(self.captchaUrl, stream= True) as captchaHtml:
                with open(self.captcha_path, 'wb') as img:
                    img.write(captchaHtml.content)
            captcha = self.captchaOCR()

            # get login data
            loginHtml = self.session.get(self.loginUrl)
            
            # check if system is open
            if '選課系統尚未開放!' in loginHtml.text:
                self.log('選課系統尚未開放!')
                continue

            # use BeautifulSoup to parse html
            parser = BeautifulSoup(loginHtml.text, 'lxml')

            # update login payload
            self.loginPayLoad['__VIEWSTATE'] = parser.select("#__VIEWSTATE")[0]['value']
            self.loginPayLoad['__VIEWSTATEGENERATOR'] = parser.select("#__VIEWSTATEGENERATOR")[0]['value']
            self.loginPayLoad['__EVENTVALIDATION'] = parser.select("#__EVENTVALIDATION")[0]['value']
            self.loginPayLoad['DPL_SelCosType'] = parser.select("#DPL_SelCosType option")[1]['value']
            self.loginPayLoad['Txt_CheckCode'] = captcha

            result = self.session.post(self.loginUrl, data= self.loginPayLoad)
            if ("parent.location ='SelCurr.aspx?Culture=zh-tw'" in result.text): #成功登入訊息可能一直改，挑個不太能改的
                self.log('Login Successful! {}'.format(captcha))
                break
            elif ("資料庫發生異常" in result.text): # 僅比較成功登入及帳號密碼錯誤的訊息，不確定是否還有其他種情況也符合這個條件
                self.log('帳號或密碼錯誤，請重新確認。')
            elif ("您未在此階段選課時程之內!請於時程內選課!!" in result.text):
                self.log('您未在此階段選課時程之內!請於時程內選課!!')
            else:
                self.log("Login Failed, Re-try!")
                continue
            return False  # Login failed with error

        return True  # Login successful

    def getCourseDB(self, depts):

        for dept in depts:
            # use BeautifulSoup to parse html
            html = self.session.get(self.courseListUrl)
            if "異常登入" in html.text:
                self.log("異常登入，休息10分鐘!")
                time.sleep(600) # sleep 10 min
                continue
            parser = BeautifulSoup(html.text, 'lxml')

            self.selectPayLoad[dept] = {
                '__EVENTTARGET': 'DPL_Degree',
                '__EVENTARGUMENT': '',
                '__LASTFOCUS': '',
                '__VIEWSTATE': parser.select("#__VIEWSTATE")[0]['value'],
                '__VIEWSTATEGENERATOR': parser.select("#__VIEWSTATEGENERATOR")[0]['value'],
                '__VIEWSTATEENCRYPTED': '',
                '__EVENTVALIDATION': parser.select("#__EVENTVALIDATION")[0]['value'],
                'Hidden1': '',
                'Hid_SchTime': '',
                'DPL_DeptName': dept,
                'DPL_Degree': '6',
            }

            # use BeautifulSoup to parse html
            html = self.session.post(self.courseListUrl, data= self.selectPayLoad[dept])
            if "Error" in html.text:
                self.log('Wrong coursesList, please check it again!')
                return False
            parser = BeautifulSoup(html.text, 'lxml')

            # parse and save courses information
            courseList = parser.select("#CosListTable input")
            for courseInfo in courseList:
                tokens = courseInfo.attrs['name'].split(',') # SelCos,CS354,A,1,F,3,Y,Chinese,CS354,A,3 電腦與網路安全概論

                key = tokens[1] + tokens[2]
                courseName = '{} {}'.format(key, tokens[-1].split(' ')[1])

                self.coursesDB[key] = {
                    'name': courseName,
                    'mUrl': courseInfo.attrs['name']
                }
                # self.log(self.coursesDB[key])

            self.log('Get {} Data Completed!'.format(dept))

        return True


    def selectCourses(self, coursesList, delay = 0):
        while len(coursesList) > 0:
            for course in coursesList.copy():
                tokens = course.split(',')
                dept = tokens[0]
                key  = tokens[1]
                
                # check if the classID is legal
                if key not in self.coursesDB:
                    self.log('{} is not a legal classID'.format(key))
                    coursesList.remove(course)
                    continue
                
                # simulte click button
                html = self.session.post(self.courseListUrl, data= self.selectPayLoad[dept])
                parser = BeautifulSoup(html.text, 'lxml')

                selectPayLoad = {
                    '__EVENTTARGET': '',
                    '__EVENTARGUMENT': '',
                    '__LASTFOCUS': '',
                    '__VIEWSTATE': parser.select("#__VIEWSTATE")[0]['value'],
                    '__VIEWSTATEGENERATOR': parser.select("#__VIEWSTATEGENERATOR")[0]['value'],
                    '__VIEWSTATEENCRYPTED': '',
                    '__EVENTVALIDATION': parser.select("#__EVENTVALIDATION")[0]['value'],
                    'Hidden1': '',
                    'Hid_SchTime': '',
                    'DPL_DeptName': dept,
                    'DPL_Degree': '6',
                    self.coursesDB[key]['mUrl'] + '.x': '0', 
                    self.coursesDB[key]['mUrl'] + '.y': '0'
                }
                self.session.post(self.courseListUrl, data= selectPayLoad)

                # select course
                html = self.session.get(self.courseSelectUrl + self.coursesDB[key]['mUrl'] + ' ,B,')

                # check if successful
                parser = BeautifulSoup(html.text, 'lxml')
                alertMsg = parser.select("script")[0].string.split(';')[0]
                self.log('{} {}'.format(self.coursesDB[key]['name'], alertMsg[7:-2]))

                if "加選訊息：" in alertMsg or "已選過" in alertMsg:
                    coursesList.remove(course)
                elif "please log on again!" in alertMsg:
                    if not self.login():
                        return

                time.sleep(delay)

    def log(self, msg):
        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]", time.localtime())
        full_msg = f"{timestamp} {msg}"
        print(full_msg)
        if self.log_callback:
            self.log_callback(full_msg)


class CourseBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("元智大學選課機器人")
        self.root.geometry("600x650")
        self.root.resizable(False, False)
        
        self.running = False
        self.bot_thread = None
        
        # 設置樣式
        self.setup_ui()
        
    def setup_ui(self):
        # 標題
        title_label = tk.Label(
            self.root, 
            text="元智大學選課機器人", 
            font=("Microsoft JhengHei", 16, "bold"),
            pady=10
        )
        title_label.pack()
        
        # 主要框架
        main_frame = tk.Frame(self.root, padx=20, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 帳號
        account_frame = tk.Frame(main_frame)
        account_frame.pack(fill=tk.X, pady=5)
        tk.Label(account_frame, text="帳號：", width=15, anchor='w', font=("Microsoft JhengHei", 10)).pack(side=tk.LEFT)
        self.account_entry = tk.Entry(account_frame, font=("Microsoft JhengHei", 10))
        self.account_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 密碼
        password_frame = tk.Frame(main_frame)
        password_frame.pack(fill=tk.X, pady=5)
        tk.Label(password_frame, text="密碼：", width=15, anchor='w', font=("Microsoft JhengHei", 10)).pack(side=tk.LEFT)
        self.password_entry = tk.Entry(password_frame, show="*", font=("Microsoft JhengHei", 10))
        self.password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 課程清單
        courses_label = tk.Label(
            main_frame, 
            text="課程清單（每行一個，格式：部門代碼,課程代碼）：", 
            anchor='w',
            font=("Microsoft JhengHei", 10)
        )
        courses_label.pack(fill=tk.X, pady=(10, 2))
        
        courses_example = tk.Label(
            main_frame,
            text="範例：312,EEB219A",
            anchor='w',
            font=("Microsoft JhengHei", 8),
            fg="gray"
        )
        courses_example.pack(fill=tk.X, pady=(0, 5))
        
        self.courses_text = scrolledtext.ScrolledText(
            main_frame, 
            height=6, 
            font=("Consolas", 10),
            wrap=tk.WORD
        )
        self.courses_text.pack(fill=tk.BOTH, pady=5)
        self.courses_text.insert(tk.END, "312,EEB219A")
        
        # 延遲時間
        delay_frame = tk.Frame(main_frame)
        delay_frame.pack(fill=tk.X, pady=5)
        tk.Label(delay_frame, text="延遲時間（秒）：", width=15, anchor='w', font=("Microsoft JhengHei", 10)).pack(side=tk.LEFT)
        self.delay_entry = tk.Entry(delay_frame, font=("Microsoft JhengHei", 10))
        self.delay_entry.insert(0, "2.5")
        self.delay_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 開始按鈕
        self.start_button = tk.Button(
            main_frame,
            text="開始選課",
            command=self.start_bot,
            font=("Microsoft JhengHei", 12, "bold"),
            bg="#4CAF50",
            fg="white",
            activebackground="#45a049",
            pady=10,
            cursor="hand2"
        )
        self.start_button.pack(fill=tk.X, pady=10)
        
        # 執行記錄
        log_label = tk.Label(
            main_frame,
            text="執行記錄：",
            anchor='w',
            font=("Microsoft JhengHei", 10, "bold")
        )
        log_label.pack(fill=tk.X, pady=(10, 5))
        
        self.log_text = scrolledtext.ScrolledText(
            main_frame,
            height=12,
            font=("Consolas", 9),
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
    def log_message(self, message):
        """在 GUI 中顯示日誌訊息"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update()
        
    def validate_inputs(self):
        """驗證輸入"""
        if not self.account_entry.get().strip():
            messagebox.showerror("錯誤", "請輸入帳號！")
            return False
            
        if not self.password_entry.get().strip():
            messagebox.showerror("錯誤", "請輸入密碼！")
            return False
            
        courses = self.courses_text.get("1.0", tk.END).strip()
        if not courses:
            messagebox.showerror("錯誤", "請輸入至少一個課程！")
            return False
            
        try:
            delay = float(self.delay_entry.get())
            if delay < 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("錯誤", "延遲時間必須是非負數！")
            return False
            
        # 檢查 model.h5 是否存在（使用正確的資源路徑）
        model_path = resource_path('model.h5')
        if not os.path.isfile(model_path):
            messagebox.showerror("錯誤", "找不到 model.h5 檔案！\n請確保程式完整下載。")
            return False
            
        return True
        
    def start_bot(self):
        """開始執行選課機器人"""
        if self.running:
            messagebox.showinfo("提示", "選課機器人正在運行中...")
            return
            
        if not self.validate_inputs():
            return
            
        # 清空日誌
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        
        # 禁用按鈕和輸入框
        self.start_button.config(state=tk.DISABLED, text="選課中...", bg="gray")
        self.account_entry.config(state=tk.DISABLED)
        self.password_entry.config(state=tk.DISABLED)
        self.courses_text.config(state=tk.DISABLED)
        self.delay_entry.config(state=tk.DISABLED)
        
        self.running = True
        
        # 在新線程中運行機器人
        self.bot_thread = Thread(target=self.run_bot, daemon=True)
        self.bot_thread.start()
        
    def run_bot(self):
        """在背景線程中運行機器人"""
        try:
            # 獲取輸入值
            account = self.account_entry.get().strip()
            password = self.password_entry.get().strip()
            courses_text = self.courses_text.get("1.0", tk.END).strip()
            delay = float(self.delay_entry.get())
            
            # 解析課程清單
            coursesList = [line.strip() for line in courses_text.split('\n') if line.strip()]
            
            self.log_message("=" * 50)
            self.log_message("開始執行選課機器人")
            self.log_message(f"課程數量：{len(coursesList)}")
            self.log_message("=" * 50)
            
            # 獲取部門列表
            depts = set([i.split(',')[0] for i in coursesList])
            
            # 創建機器人實例
            myBot = CourseBot(account, password, log_callback=self.log_message)
            
            # 登入
            self.log_message("正在登入...")
            if not myBot.login():
                self.log_message("登入失敗！")
                self.finish_bot()
                return
                
            # 獲取課程資料
            self.log_message("正在獲取課程資料...")
            if not myBot.getCourseDB(depts):
                self.log_message("獲取課程資料失敗！")
                self.finish_bot()
                return
                
            # 開始選課
            self.log_message("開始選課...")
            myBot.selectCourses(coursesList, delay)
            
            self.log_message("=" * 50)
            self.log_message("選課流程結束！")
            self.log_message("=" * 50)
            
        except Exception as e:
            self.log_message(f"發生錯誤：{str(e)}")
            import traceback
            self.log_message(traceback.format_exc())
        finally:
            self.finish_bot()
            
    def finish_bot(self):
        """完成選課，恢復 UI 狀態"""
        self.running = False
        self.start_button.config(state=tk.NORMAL, text="開始選課", bg="#4CAF50")
        self.account_entry.config(state=tk.NORMAL)
        self.password_entry.config(state=tk.NORMAL)
        self.courses_text.config(state=tk.NORMAL)
        self.delay_entry.config(state=tk.NORMAL)


if __name__ == '__main__':
    root = tk.Tk()
    app = CourseBotGUI(root)
    root.mainloop()

