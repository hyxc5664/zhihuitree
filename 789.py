import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    StaleElementReferenceException,
    WebDriverException,
    TimeoutException,
    ElementClickInterceptedException,

)

COURSE_URL = (
    "https://studyvideoh5.zhihuishu.com/stuStudy"
    "?recruitAndCourseId=4e5d585c42504859454a5859584159435b"
)

# 如果 geckodriver 已加入 PATH，设置为 None。
# 否则填写实际路径，例如：
# GECKODRIVER_PATH = r"D:\WebDriver\geckodriver.exe"
GECKODRIVER_PATH = None

PROFILE_DIR = Path("./zhihuishu_firefox_profile").resolve()


# =========================
# 启动 Firefox
# =========================

def create_driver():
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    options = webdriver.FirefoxOptions()
    options.add_argument("-width=1440")
    options.add_argument("-height=900")

    if GECKODRIVER_PATH:
        service = Service(executable_path=GECKODRIVER_PATH)
    else:
        service = Service()

    driver = webdriver.Firefox(
        service=service,
        options=options,
    )

    driver.set_page_load_timeout(60)
    return driver

def play_current_video(driver):
    """
    检测当前页面的视频，读取视频信息并启动播放。
    返回 True 表示视频播放完成，False 表示无法继续。
    """

    wait = WebDriverWait(driver, 20)

    # 1. 检查 HTML5 视频是否存在
    try:
        video = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "video")
            )
        )
    except TimeoutException:
        print("未检测到 HTML5 video 元素。")
        return False

    # 2. 读取视频信息
    try:
        info = driver.execute_script("""
            const v = arguments[0];
            return {
                src: v.currentSrc || v.src,
                paused: v.paused,
                ended: v.ended,
                currentTime: v.currentTime,
                duration: v.duration,
                readyState: v.readyState
            };
        """, video)

        print("\n========== 当前视频信息 ==========")
        for key, value in info.items():
            print(f"{key}: {value}")

    except StaleElementReferenceException:
        print("视频元素已发生变化，请重新检测。")
        return False

    # 3. 获取视频区域
    try:
        video_area = wait.until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, ".videoArea")
            )
        )
    except TimeoutException:
        print("未检测到可见的视频区域。")
        return False

    # 4. 如果视频尚未播放，则单击视频区域启动播放
    try:
        paused = driver.execute_script(
            "return arguments[0].paused;", video
        )

        if paused and not info["ended"]:
            ActionChains(driver) \
                .move_to_element(video_area) \
                .click() \
                .perform()

            print("已单击视频区域，尝试启动播放。")

    except StaleElementReferenceException:
        print("视频元素已更新，请重新检测。")
        return False

    # 5. 等待视频播放完成
    # 每 3 秒检查一次播放状态；不使用固定视频时长进行 sleep
    print("等待视频播放完成……")

    while True:

        # 1. 检测弹题弹窗
        if detect_question_popup(driver, timeout=0.2):
            print("播放期间检测到弹题弹窗。")

            # 2. 处理弹窗
            inspect_video_area(driver)

            # 3. 确认弹窗关闭
            dialog_selector = (
                'div.el-dialog[role="dialog"][aria-label="弹题测验"]'
            )

            try:
                WebDriverWait(driver, 5).until(
                    EC.invisibility_of_element_located(
                        (By.CSS_SELECTOR, dialog_selector)
                    )
                )
                print("弹窗已关闭，恢复视频监测。")

            except TimeoutException:
                print("弹窗仍未关闭，重新检测。")
                time.sleep(3)
                continue

            # 4. 重新获取视频元素
            try:
                video = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "video")
                    )
                )
            except TimeoutException:
                print("暂时未找到视频元素，继续监测。")
                continue

            # 5. 返回循环开头，监测下一次弹窗
            continue

        # 6. 没有弹窗时，检查视频播放状态（每 3 秒一次）
        try:
            state = driver.execute_script("""
                const v = arguments[0];
                return {
                    ended: v.ended,
                    paused: v.paused,
                    currentTime: v.currentTime,
                    duration: v.duration
                };
            """, video)

            if state["ended"]:
                print("视频播放完成。")
                return True

            # 7. 如果视频不是播放状态（暂停/未开始），单击视频区域尝试恢复播放
            if state["paused"]:
                print(
                    f"检测到视频未播放（paused=True，"
                    f"currentTime={state['currentTime']:.1f}/"
                    f"{state['duration']:.1f}），单击视频区域尝试恢复播放。"
                )

                try:
                    video_area = WebDriverWait(driver, 3).until(
                        EC.visibility_of_element_located(
                            (By.CSS_SELECTOR, ".videoArea")
                        )
                    )
                    ActionChains(driver) \
                        .move_to_element(video_area) \
                        .click() \
                        .perform()

                except (TimeoutException, StaleElementReferenceException):
                    print("未找到可点击的视频区域，继续监测。")

            time.sleep(3)

        except StaleElementReferenceException:
            print("视频元素已更新，重新获取。")

            try:
                video = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "video")
                    )
                )
            except TimeoutException:
                continue

def detect_question_popup(driver, timeout=3):
    """检测页面中是否出现可见的弹题测验弹窗。"""
    driver.switch_to.default_content()

    dialog_locator = (
        By.CSS_SELECTOR,
        'div.el-dialog[role="dialog"][aria-label="弹题测验"]'
    )

    try:
        dialog = WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located(dialog_locator)
        )

        print("检测到弹题测验弹窗")
        print("弹窗标题：", dialog.get_attribute("aria-label"))
        print(
            "题目数量：",
            len(dialog.find_elements(By.CSS_SELECTOR, "li.topic-item"))
        )
        return True

    except TimeoutException:

        return False

    except WebDriverException as exc:
        print("检测弹窗时发生 WebDriver 错误：", exc)
        return False



def inspect_video_area(driver):
    """
    检查 videoArea 是否存在、可见，以及 HTML5 video 的状态。
    随后依次点击 A、B、C、D，点击关闭按钮，
    最后单击视频区域。
    """

    driver.switch_to.default_content()

    wait = WebDriverWait(driver, 10)

    areas = driver.find_elements(
        By.CSS_SELECTOR,
        ".videoArea"
    )

    print("\n========== 视频区域 ==========")

    if areas:
        for index, area in enumerate(areas, start=1):
            try:
                print(
                    f"区域 {index}："
                    f"可见={area.is_displayed()}，"
                    f"尺寸={area.size}"
                )
            except StaleElementReferenceException:
                print(f"区域 {index} 在检查期间发生变化。")
    else:
        print("主页面未发现 .videoArea，可能位于 iframe 中。")

    videos = driver.find_elements(
        By.CSS_SELECTOR,
        "video"
    )

    if not videos:
        print("主页面没有发现 HTML5 video 元素。")
    else:
        for index, video in enumerate(videos, start=1):
            try:
                state = driver.execute_script(
                    """
                    const v = arguments[0];
                    return {
                        paused: v.paused,
                        ended: v.ended,
                        currentTime: v.currentTime,
                        duration: v.duration,
                        readyState: v.readyState
                    };
                    """,
                    video,
                )

                print(f"视频 {index} 状态：{state}")

            except WebDriverException as exc:
                print(f"读取视频 {index} 状态失败：{exc}")

    # ===== 依次检测并点击 A、B、C、D =====
    print("\n========== 处理选项 ==========")

    time.sleep(0.5)

    for option_letter in ["A", "B", "C", "D"]:
        option_xpath = (
            "//li[contains(@class, 'topic-item')]"
            f"[.//span[contains(@class, 'topic-option-item') "
            f"and normalize-space()='{option_letter}.']]"
        )

        try:
            # 先检查选项是否存在，不存在则跳过，不中断后续操作
            options = driver.find_elements(By.XPATH, option_xpath)

            if not options:
                print(f"未检测到选项 {option_letter}，跳过。")
                continue

            # 等待选项可点击
            # 等待选项可见且启用
            option = wait.until(
                EC.element_to_be_clickable((By.XPATH, option_xpath))
            )

            # 滚动到视口中央，避免落在页面底部的遮挡区域
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
                option,
            )

            try:
                option.click()
                print(f"已点击选项 {option_letter}")
            except ElementClickInterceptedException:
                print(f"选项 {option_letter} 被其他元素遮挡，跳过。")

        except TimeoutException:
            print(f"选项 {option_letter} 不可点击，跳过。")

        except StaleElementReferenceException:
            print(f"选项 {option_letter} 页面元素已刷新，跳过。")

    # ===== 移动鼠标到右上角关闭按钮并点击 =====
    time.sleep(0.5)

    dialog_selector = (
        'div.el-dialog[role="dialog"][aria-label="弹题测验"]'
    )

    try:
        # 等待弹窗显示
        dialog = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, dialog_selector)
            )
        )

        # 根据你提供的 HTML 定位右上角关闭按钮
        close_button = dialog.find_element(
            By.CSS_SELECTOR,
            "button.el-dialog__headerbtn"
        )

        # 移动鼠标到按钮上，然后点击
        ActionChains(driver) \
            .move_to_element(close_button) \
            .pause(0.3) \
            .click() \
            .perform()

        # 等待弹窗真正消失
        WebDriverWait(driver, 5).until(
            EC.invisibility_of_element_located(
                (By.CSS_SELECTOR, dialog_selector)
            )
        )

        print("弹题测验弹窗已成功关闭")

    except TimeoutException:
        print("等待弹窗或关闭操作超时")

    except WebDriverException as exc:
        print("关闭弹窗失败：", exc)
    # ===== 最后单击视频区域 =====
    time.sleep(1)

    try:
        video_area = wait.until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, ".videoArea")
            )
        )

        ActionChains(driver) \
            .move_to_element(video_area) \
            .click() \
            .perform()

        print("已单击 videoArea 区域")

    except TimeoutException:
        print("未找到可见的 videoArea 区域。")


def click_next_video(driver):
    """
    视频结束后逐渐移动鼠标，并在移动过程中持续检测下一视频按钮。
    检测到按钮可点击时，立即停止移动并点击。
    """

    wait = WebDriverWait(driver, 20)

    dialog_selector = (
        'div.el-dialog[role="dialog"][aria-label="弹题测验"]'
    )

    # ===== 1. 确认弹题弹窗已关闭 =====
    try:
        WebDriverWait(driver, 3).until(
            EC.invisibility_of_element_located(
                (By.CSS_SELECTOR, dialog_selector)
            )
        )
    except TimeoutException:
        print("弹题弹窗仍然存在，暂不切换视频。")
        return False

    # ===== 2. 记录当前视频状态 =====
    old_state = driver.execute_script("""
        const v = document.querySelector("video");
        if (!v) return null;

        return {
            src: v.currentSrc || v.src,
            currentTime: v.currentTime,
            duration: v.duration,
            ended: v.ended
        };
    """)

    if old_state is None:
        print("未找到当前视频。")
        return False

    print("切换前的视频状态：", old_state)

    # ===== 3. 定位视频区域 =====
    try:
        video_area = wait.until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, ".videoArea")
            )
        )
    except TimeoutException:
        print("未找到可见的视频区域。")
        return False

    # ===== 4. 定义按钮检测与点击函数 =====
    def try_click_next():
        buttons = driver.find_elements(By.ID, "nextBtn")

        for btn in buttons:
            try:
                if not btn.is_displayed() or not btn.is_enabled():
                    continue

                # 检查按钮是否被其他元素遮挡
                clickable = driver.execute_script("""
                    const el = arguments[0];
                    const r = el.getBoundingClientRect();

                    if (r.width <= 0 || r.height <= 0) {
                        return false;
                    }

                    const x = r.left + r.width / 2;
                    const y = r.top + r.height / 2;
                    const top = document.elementFromPoint(x, y);

                    return top === el || el.contains(top);
                """, btn)

                if not clickable:
                    continue

                btn.click()
                print("检测到下一视频按钮，已立即点击。")
                return True

            except (
                StaleElementReferenceException,
                ElementClickInterceptedException
            ):
                continue

        return False

    # ===== 5. 获取移动起点和目标位置 =====
    try:
        # 先将鼠标移动到视频区域中心
        ActionChains(driver).move_to_element(
            video_area
        ).pause(0.3).perform()

        start = driver.execute_script("""
            const r = arguments[0].getBoundingClientRect();

            return {
                x: r.left + r.width / 2,
                y: r.top + r.height / 2
            };
        """, video_area)

        # 先检测按钮，避免按钮已经出现却仍然移动鼠标
        if try_click_next():
            clicked = True
        else:
            clicked = False

            # 使用视频区域中心作为起点。
            # 目标设置为视频区域右侧附近，移动过程中反复检测按钮。
            target = driver.execute_script("""
                const r = arguments[0].getBoundingClientRect();

                return {
                    x: r.left + r.width * 0.9,
                    y: r.top + r.height * 0.5
                };
            """, video_area)

            steps = 30
            print("开始逐渐移动鼠标并监测下一视频按钮……")

            for i in range(1, steps + 1):
                # 移动前检查
                if try_click_next():
                    clicked = True
                    break

                # 计算本次应移动的相对距离
                dx = round(
                    (target["x"] - start["x"]) / steps
                )
                dy = round(
                    (target["y"] - start["y"]) / steps
                )

                if dx != 0 or dy != 0:
                    ActionChains(driver) \
                        .move_by_offset(dx, dy) \
                        .pause(0.08) \
                        .perform()
                else:
                    time.sleep(0.08)

                # 移动后检查
                if try_click_next():
                    clicked = True
                    break

            # ===== 6. 移动结束后继续等待按钮 =====
            if not clicked:
                print("移动结束，继续等待下一视频按钮。")

                deadline = time.monotonic() + 15

                while time.monotonic() < deadline:
                    if try_click_next():
                        clicked = True
                        break

                    time.sleep(0.2)

        if not clicked:
            print("未能找到可点击的下一视频按钮。")
            buttons = driver.find_elements(By.ID, "nextBtn")
            print("按钮数量：", len(buttons))

            for btn in buttons:
                try:
                    print(
                        "可见：", btn.is_displayed(),
                        "启用：", btn.is_enabled(),
                        "HTML：", btn.get_attribute("outerHTML")
                    )
                except WebDriverException:
                    pass

            return False

    except (TimeoutException, WebDriverException) as exc:
        print("鼠标移动或按钮检测失败：", exc)
        return False

    # ===== 7. 确认视频已切换 =====
    try:
        wait.until(lambda d: d.execute_script("""
            const v = document.querySelector("video");
            if (!v) return false;

            const old = arguments[0];
            const src = v.currentSrc || v.src;

            return (
                src !== old.src ||
                (v.currentTime < 1 && !v.ended)
            );
        """, old_state))

        print("已检测到下一个视频切换或播放进度重置。")
        return True

    except TimeoutException:
        print("按钮已点击，但未能确认视频切换。")
        return False


def main_video_loop(driver, max_videos=100):
    """
    循环处理课程视频：
    检测视频 -> 播放 -> 播放完成 -> 点击下一视频。
    max_videos 用于限制本次运行最多处理的视频数。
    """

    for index in range(1, max_videos + 1):
        print(f"\\n========== 第 {index} 个视频 ==========")

        # 检测并播放当前视频
        completed = play_current_video(driver)


        if detect_question_popup(driver, timeout=3):
            print("检测到弹窗，先执行弹窗处理流程。")
            inspect_video_area(driver)
        else:
            print("未检测到弹窗。")

        if not completed:
            print("当前视频未能正常完成，停止循环。")
            break

        # 播放完成后进入下一个视频
        if index < max_videos:
            moved = click_next_video(driver)

            if not moved:
                print("无法确认下一个视频已加载，停止循环。")
                break


    print("视频处理循环结束。")

def main():
    driver = create_driver()

    try:
        # 打开课程页面
        driver.get(COURSE_URL)
        print("课程页面已打开。")

        # 等待手动登录
        input("请在浏览器中手动登录并进入课程页面，准备好后按 Enter 继续……")

        # 开始视频处理循环
        main_video_loop(driver, max_videos=100)

    except KeyboardInterrupt:
        print("\n用户手动停止程序。")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()