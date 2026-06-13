"""
TCP File Reversal Server
支持多客户端并发处理，反转客户端发送的文本块
"""

import socket
import threading    # 多线程库，实现同时处理多个客户端。
import struct
import time
import os
import signal
import select   # IO多路复用，让服务端可以响应退出信号。
import fcntl    # 文件锁

# 报文类型常量
MSG_INIT = 1
MSG_AGREE = 2
MSG_REV_REQ = 3
MSG_REV_ANS = 4

# 日志文件
LOG_FILE = "run_log.txt"

# 退出标志
should_exit = False


def write_log(msg):
    """线程安全的日志写入"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    log_line = f"[{timestamp}] {msg}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(log_line)
            f.flush()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    print(log_line.strip())
    time.sleep(0.001)


def handle_ctrl_c(signum, frame):
    """Ctrl+C 信号处理"""
    global should_exit
    should_exit = True
    write_log("[SERVER] 收到 Ctrl+C，设置退出标志...")


# 按下Ctrl+C、系统终止程序时，都执行退出函数。
signal.signal(signal.SIGINT, handle_ctrl_c)
signal.signal(signal.SIGTERM, handle_ctrl_c)


def recv_all(conn, n):
    """可靠接收 n 字节数据，支持超时检查退出"""
    data = b""
    while len(data) < n:
        if should_exit:
            return None
        # 设置接收超时，定期检查退出标志
        conn.settimeout(1.0)
        try:
            packet = conn.recv(n - len(data))
        except socket.timeout:
            continue
        except OSError:
            return None
        finally:
            conn.settimeout(None)
        if not packet:
            return None
        data += packet
    return data


def parse_init_message(data):
    """解析 Initialization 报文: Type(2B) + N(4B)"""
    msg_type = struct.unpack(">H", data[0:2])[0]
    n = struct.unpack(">I", data[2:6])[0]
    return msg_type, n


def build_agree_message():
    """构造 agree 报文: Type(2B)"""
    return struct.pack(">H", MSG_AGREE)


def build_rev_answer(reversed_data):
    """构造 reverseAnswer 报文: Type(2B) + Length(4B) + reverseData"""
    length = len(reversed_data)
    return struct.pack(">H", MSG_REV_ANS) + struct.pack(">I", length) + reversed_data


def handle_client(conn, addr):
    """处理单个客户端连接"""
    client_id = f"{addr[0]}:{addr[1]}"
    write_log(f"[SERVER] 新客户端连接: {client_id}")

    try:
        # 接收Initialization报文 (2B Type + 4B N = 6B)
        init_data = recv_all(conn, 6)
        if init_data is None:
            write_log(f"[SERVER] 客户端 {client_id} 断开连接(INIT)")
            return

        msg_type, n = parse_init_message(init_data)
        write_log(f"[SERVER] 收到 Initialization | Type={msg_type}, N={n}, 长度=6B | 来自 {client_id}")

        # 发送agree报文 (2B)
        agree_msg = build_agree_message()
        conn.sendall(agree_msg)
        write_log(f"[SERVER] 发送 agree | Type={MSG_AGREE}, 长度=2B | 至 {client_id}")

        # 循环处理reverseRequest
        for i in range(n):
            if should_exit:
                write_log(f"[SERVER] 收到退出信号，中断处理客户端 {client_id}")
                break

            # 接收Type (2B)
            type_data = recv_all(conn, 2)
            if type_data is None:
                write_log(f"[SERVER] 客户端 {client_id} 在接收第{i+1}块时断开")
                break

            msg_type = struct.unpack(">H", type_data)[0]

            # 接收Length (4B)
            len_data = recv_all(conn, 4)
            if len_data is None:
                write_log(f"[SERVER] 客户端 {client_id} 在接收长度时断开")
                break

            length = struct.unpack(">I", len_data)[0]

            # 接收Data
            req_data = recv_all(conn, length)
            if req_data is None:
                write_log(f"[SERVER] 客户端 {client_id} 在接收数据时断开")
                break

            write_log(f"[SERVER] 收到 reverseRequest | Type={msg_type}, Length={length}, 总长度={6+length}B | 来自 {client_id}")

            # 直接对字节流进行反转
            reversed_data = req_data[::-1]

            # 发送reverseAnswer
            ans_msg = build_rev_answer(reversed_data)
            conn.sendall(ans_msg)
            ans_length = len(reversed_data)
            write_log(f"[SERVER] 发送 reverseAnswer | Type={MSG_REV_ANS}, Length={ans_length}, 总长度={6+ans_length}B | 至 {client_id}")

        write_log(f"[SERVER] 客户端 {client_id} 处理完成")

    except Exception as e:
        write_log(f"[SERVER] 处理客户端 {client_id} 时出错: {e}")
    finally:
        conn.close()
        write_log(f"[SERVER] 关闭与 {client_id} 的连接")


def start_server(host="0.0.0.0", port=12345):
    """启动 TCP 服务器"""
    global should_exit
    should_exit = False

    # 清空或创建日志文件
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== Server Log Started at {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # 允许端口复用，重启程序不会报端口占用。
    server_socket.bind((host, port))
    server_socket.listen(5)

    write_log(f"[SERVER] 服务器启动，监听 {host}:{port}")
    write_log("[SERVER] 等待客户端连接... (按 Ctrl+C 停止)")

    try:
        while not should_exit:
            # 使用select实现超时，让accept可以被Ctrl+C中断
            # 超时时间1秒，定期检查should_exit标志
            readable, _, _ = select.select([server_socket], [], [], 1.0)
            if not readable:
                continue  # 超时，检查should_exit

            conn, addr = server_socket.accept()
            client_thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.daemon = True
            client_thread.start()
            write_log(f"[SERVER] 为客户端 {addr[0]}:{addr[1]} 启动新线程 (当前活动线程数: {threading.active_count()})")

    except Exception as e:
        write_log(f"[SERVER] 服务器异常: {e}")
    finally:
        server_socket.close()
        write_log("[SERVER] 服务器 socket 已关闭")

    # 等待所有客户端线程结束（最多等3秒）
    write_log("[SERVER] 等待客户端线程结束...")
    main_thread = threading.current_thread()
    for t in threading.enumerate():
        if t is not main_thread and t.is_alive():
            t.join(timeout=3)
    write_log("[SERVER] 服务器已完全退出")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TCP File Reversal Server")
    parser.add_argument("--host", default="0.0.0.0", help="监听IP (默认: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=12345, help="监听端口 (默认: 12345)")
    args = parser.parse_args()

    start_server(args.host, args.port)
