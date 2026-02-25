import os  # даёт доступ к переменным окружения через os.getenv()
from pathlib import Path  # удобная работа с путями (Windows/Linux одинаково)
import pytest  # фреймворк тестов + фикстуры
from selenium import webdriver  # запускает и управляет браузером
from selenium.webdriver.common.by import By  # стратегии поиска элементов (ID, XPATH и т.д.)
from selenium.webdriver.chrome.options import Options  # настройки запуска Chrome
from selenium.webdriver.support.ui import WebDriverWait  # "явные ожидания" (wait until ...)
from selenium.webdriver.support import expected_conditions as EC  # готовые условия ожиданий
from selenium.common.exceptions import TimeoutException  # ошибка, если ожидание не выполнилось


LOGIN_URL = "https://dev.base86.com/auth/sign-in"  # адрес страницы логина
LOGIN_PATH_PART = "/auth/sign-in"  # кусок URL, по которому поймём "мы ещё на странице логина"

EMAIL_ID = "sign-in_email"  # id поля email (как у тебя в коде)
PASSWORD_ID = "sign-in_password"  # id поля password (как у тебя в коде)

# XPATH кнопки Login: ищем <button>, внутри которого есть <span> с текстом "Login"
LOGIN_BUTTON_XPATH = "//button[.//span[normalize-space()='Login']]"


def login_form_is_visible(driver) -> bool:
    """
    Проверяем, видна ли форма логина прямо сейчас.
    True = поле email существует и отображается (значит мы на логине).
    False = формы нет или она скрыта (возможно уже залогинены).
    """
    elements = driver.find_elements(By.ID, EMAIL_ID)  # ищем элементы по id (может вернуть пустой список)
    return any(el.is_displayed() for el in elements)  # True, если хотя бы один найденный элемент видим


@pytest.fixture(scope="function")  # фикстура запускается для каждого теста отдельно
def driver():
    options = Options()  # создаём объект настроек Chrome

    # Пытаемся определить корень проекта.
    # Если файл лежит в E:\project\Autotest2\tests\test_login.py,
    # то parents[1] = E:\project\Autotest2
    project_root = Path(__file__).resolve().parents[1]  # абсолютный путь к корню проекта

    profile_dir = project_root / ".chrome-profile"  # папка для отдельного chrome-профиля тестов
    profile_dir.mkdir(exist_ok=True)  # создаём папку, если её ещё нет

    options.add_argument(f"--user-data-dir={profile_dir}")  # хранить сессию/куки в этой папке
    options.add_argument("--start-maximized")  # открыть окно развёрнутым

    # (опционально) параметры, иногда уменьшают "detected as automation"
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    browser = webdriver.Chrome(options=options)  # запускаем Chrome

    browser.implicitly_wait(0)  # отключаем implicit wait (мы используем только WebDriverWait)
    yield browser  # отдаём driver в тест

    browser.quit()  # закрываем браузер после завершения теста


def test_open_and_login(driver):
    username = os.getenv("QA_LOGIN")  # берём логин из переменной окружения
    password = os.getenv("QA_PASSWORD")  # берём пароль из переменной окружения

    print("DEBUG QA_LOGIN:", repr(username))
    print("DEBUG QA_PASSWORD set:", password is not None)

    wait = WebDriverWait(driver, 20)  # общий явный wait: максимум 20 секунд на ожидания

    driver.get(LOGIN_URL)  # открыть страницу логина
    print("Opened URL:", driver.current_url)  # печать текущего URL (видно при запуске с -s)

    # Ждём, пока браузер считает "документ загружен".
    # Для SPA это не гарантирует, что элементы уже появились, но это хороший старт.
    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

    # 1) Сначала пытаемся понять: есть ли форма логина?
    # Если форма есть — будем логиниться.
    # Если формы нет — вероятно уже залогинены (из-за профиля/куки).
    try:
        email_input = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.ID, EMAIL_ID))  # ждём, что поле email станет видимым
        )
        password_input = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.ID, PASSWORD_ID))  # ждём, что поле password станет видимым
        )
        form_found = True  # форма нашлась
    except TimeoutException:
        form_found = False  # форма не нашлась за 5 секунд

    # 2) Если формы НЕТ — проверяем, что мы действительно НЕ на странице логина
    if not form_found:
        # Ждём, что либо URL уже НЕ содержит /auth/sign-in,
        # либо форма реально не видна (например, сайт редиректит без смены URL — редко, но бывает).
        wait.until(lambda d: (LOGIN_PATH_PART not in d.current_url) or (not login_form_is_visible(d)))

        # Если после ожидания мы всё ещё на /auth/sign-in и форма при этом не видна — это странно.
        # Но чаще всего сюда не дойдёт.
        assert LOGIN_PATH_PART not in driver.current_url or not login_form_is_visible(driver)
        return  # тест закончен: считаем, что уже залогинены

    # 3) Если форма ЕСТЬ — требуем, чтобы креды были заданны
    assert username and password, (
        "Форма логина есть, но QA_LOGIN/QA_PASSWORD не заданы.\n"
        "В PyCharm: Run/Debug Configurations -> Environment variables.\n"
        "Должно быть:\n"
        "QA_LOGIN=your_email;QA_PASSWORD=your_password"
    )

    # 4) Находим кнопку Login, которую можно кликнуть
    login_button = wait.until(
        EC.element_to_be_clickable((By.XPATH, LOGIN_BUTTON_XPATH))  # ждём, что кнопка станет кликабельной
    )

    # 5) Вводим логин/пароль
    email_input.clear()  # очистить поле email
    email_input.send_keys(username)  # ввести email

    password_input.clear()  # очистить поле password
    password_input.send_keys(password)  # ввести пароль

    login_button.click()  # нажать Login

    # 6) Ждём результат логина:
    # Успех считаем, если:
    # - URL ушёл со страницы /auth/sign-in
    # ИЛИ
    # - форма логина стала невидимой/исчезла
    wait.until(lambda d: (LOGIN_PATH_PART not in d.current_url) or (not login_form_is_visible(d)))

    # Финальная проверка (тест "зелёный", только если действительно вышли из логина)
    assert LOGIN_PATH_PART not in driver.current_url or not login_form_is_visible(driver)
