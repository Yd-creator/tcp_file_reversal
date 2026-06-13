"""
TCP File Reversal Client
分块发送文件，接收反转后的数据，逆序拼接实现整体文件反转
"""

import socket   # 网络通信
import struct   # 打包二进制报文
import argparse # 接收命令行参数
import random   # 随机分块
import time     # 日志时间
import os       # 文件操作

# 报文类型常量
MSG_INIT = 1
MSG_AGREE = 2
MSG_REV_REQ = 3
MSG_REV_ANS = 4

# 日志文件
LOG_FILE = "run_log.txt"


def write_log(msg):
    """写入日志"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    log_line = f"[{timestamp}] {msg}\n"

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line)
        f.flush()
    print(log_line.strip())


def recv_all(conn, n):
    """可靠接收n字节数据"""
    data = b""
    try:
        while len(data) < n:
            packet = conn.recv(n - len(data))
            if not packet:
                return None
            data += packet
        return data
    except (ConnectionResetError, ConnectionAbortedError):
        return None


def build_init_message(n):
    """构造 Initialization 报文: Type(2B) + N(4B)"""
    return struct.pack(">H", MSG_INIT) + struct.pack(">I", n)


def build_rev_request(data_chunk):
    """构造 reverseRequest 报文: Type(2B) + Length(4B) + Data"""
    length = len(data_chunk)
    return struct.pack(">H", MSG_REV_REQ) + struct.pack(">I", length) + data_chunk


def parse_agree(data):
    """解析 agree 报文"""
    msg_type = struct.unpack(">H", data)[0]
    return msg_type


def parse_rev_answer(data):
    """解析 reverseAnswer 报文: Type(2B) + Length(4B) + reverseData"""
    msg_type = struct.unpack(">H", data[0:2])[0]
    length = struct.unpack(">I", data[2:6])[0]
    rev_data = data[6:6+length]
    return msg_type, length, rev_data


def split_file_into_chunks(file_path, lmin, lmax, chunk_seed):
    """
    分块算法：
    1. 读取文件所有字节
    2. 用 chunk_seed 初始化随机数生成器（确保可复现）
    3. 在 [Lmin, Lmax] 之间随机取数作为块长度
    4. 当剩余字节数 < Lmin 时，最后一块取剩余所有字节

    返回: (块列表, 总块数N)
    """
    with open(file_path, "rb") as f:
        file_data = f.read()

    total_len = len(file_data)
    write_log(f"[CLIENT] 文件总长度: {total_len} bytes")

    rng = random.Random(chunk_seed)

    chunks = []  # 创建空列表，用来存放所有文件块的信息。
    offset = 0
    chunk_num = 0

    while offset < total_len:
        remaining = total_len - offset

        if remaining < lmin:
            chunk_len = remaining
        else:
            max_possible = min(lmax, remaining)
            chunk_len = rng.randint(lmin, max_possible)

        chunk_data = file_data[offset:offset + chunk_len]
        chunks.append({
            "index": chunk_num,
            "offset": offset,
            "length": chunk_len,
            "data": chunk_data
        })

        write_log(f"[CLIENT] 第 {chunk_num + 1} 块: 偏移={offset}, 长度={chunk_len}")

        offset += chunk_len
        chunk_num += 1

    return chunks, chunk_num


def run_client(server_ip, server_port, lmin, lmax, chunk_seed, input_file, output_file):
    """客户端主流程"""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"=== Client Log Started at {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    write_log(f"[CLIENT] 连接服务器 {server_ip}:{server_port}")
    write_log(f"[CLIENT] 参数: Lmin={lmin}, Lmax={lmax}, chunk_seed={chunk_seed}")
    write_log(f"[CLIENT] 输入文件: {input_file}, 输出文件: {output_file}")

    # 分块
    chunks, n = split_file_into_chunks(input_file, lmin, lmax, chunk_seed)
    write_log(f"[CLIENT] 文件分块完成，总块数 N={n}")

    # 建立TCP连接
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server_ip, server_port))
    write_log(f"[CLIENT] TCP 连接建立成功")

    try:
        # 发送Initialization报文
        init_msg = build_init_message(n)
        sock.sendall(init_msg)
        write_log(f"[CLIENT] 发送 Initialization | Type={MSG_INIT}, N={n}, 长度=6B")

        # 接收agree报文 (2B)
        agree_data = recv_all(sock, 2)
        if agree_data is None:
            write_log("[CLIENT] 服务器断开连接")
            return

        agree_type = parse_agree(agree_data)
        write_log(f"[CLIENT] 收到 agree | Type={agree_type}, 长度=2B")

        # 循环发送reverseRequest，接收reverseAnswer
        reversed_chunks = [None] * n  # 创建长度为n的列表，用来按顺序存放每一块反转后的数据。

        for i, chunk in enumerate(chunks):
            # 构造并发送reverseRequest
            req_msg = build_rev_request(chunk["data"])
            sock.sendall(req_msg)
            req_len = len(chunk["data"])
            write_log(f"[CLIENT] 发送 reverseRequest | Type={MSG_REV_REQ}, Length={req_len}, 总长度={6+req_len}B | 第{i+1}/{n}块")

            # 接收reverseAnswer: 先读2BType + 4BLength
            header_data = recv_all(sock, 6)
            if header_data is None:
                write_log(f"[CLIENT] 服务器在接收第{i+1}块回复时断开")
                break

            msg_type = struct.unpack(">H", header_data[0:2])[0]
            length = struct.unpack(">I", header_data[2:6])[0]

            # 再读反转后的数据
            rev_data = recv_all(sock, length)
            if rev_data is None:
                write_log(f"[CLIENT] 服务器在接收第{i+1}块数据时断开")
                break

            write_log(f"[CLIENT] 收到 reverseAnswer | Type={msg_type}, Length={length}, 总长度={6+length}B | 第{i+1}/{n}块")

            # 在终端打印反转的文本
            try:
                rev_text = rev_data.decode("utf-8")
                print(f"\n>>> 第 {i+1} 块反转文本: {rev_text}")
            except UnicodeDecodeError:
                try:
                    rev_text = rev_data.decode("ascii")
                    print(f"\n>>> 第 {i+1} 块反转文本: {rev_text}")
                except UnicodeDecodeError:
                    rev_text = rev_data.decode("latin-1")
                    print(f"\n>>> 第 {i+1} 块反转数据 (latin-1): {rev_text}")

            # 存储反转结果（按块索引存储）
            reversed_chunks[i] = rev_data

        # 逆序拼接所有反转块，实现整体文件反转
        result_buffer = bytearray()
        for i in range(n - 1, -1, -1):
            result_buffer.extend(reversed_chunks[i])

        # 保存完整反转文件
        with open(output_file, "wb") as f:
            f.write(result_buffer)

        write_log(f"[CLIENT] 反转文件已保存至: {output_file}, 总大小: {len(result_buffer)} bytes")
        write_log("[CLIENT] 所有块处理完成，连接关闭")

    except Exception as e:
        write_log(f"[CLIENT] 错误: {e}")
    finally:
        sock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TCP File Reversal Client")
    parser.add_argument("serverIP", help="服务器IP地址")
    parser.add_argument("serverPort", type=int, help="服务器端口号")
    parser.add_argument("Lmin", type=int, help="最小块长度")
    parser.add_argument("Lmax", type=int, help="最大块长度")
    parser.add_argument("inputFile", help="输入文件路径")
    parser.add_argument("outputFile", help="输出文件路径")
    parser.add_argument("--chunk-seed", type=int, default=42, help="分块随机种子 (默认: 42)")

    args = parser.parse_args()

    run_client(
        args.serverIP,
        args.serverPort,
        args.Lmin,
        args.Lmax,
        args.chunk_seed,
        args.inputFile,
        args.outputFile
    )
