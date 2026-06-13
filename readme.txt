========================================
TCP 文件反转服务 
========================================

一、运行环境
Python 版本: Python 3.7+
依赖: 仅使用 Python 标准库 (socket, threading, struct, argparse, random, time, os)
操作系统: Windows 、虚拟机VMware上的ubuntu中运行

二、文件说明
server.py             - TCP 服务器端程序，支持多线程并发处理多个客户端
client.py              - TCP 客户端程序，支持分块发送、接收反转数据、逆序拼接实现整体反转
test_input.txt      - 全英文ASCII字符测试文件
run_log.txt          - 运行时自动生成的日志文件（记录所有收发报文的时间和类型）
test_output.txt   - 保存服务器端反转后的数据

三、报文格式（大端序）
---------------------------------------------------------------------------------------------------
|      报文类型          |    Type(2B) 	| 		其他字段             	| 			说明                    	|
|-------------------|--------------	|-----------------------------|----------------------------------|
| Initialization      	|          1       	| N(4B)                 			| N 是要反转的总块数      		|
| agree                  	| 	   2        	| 无                    			| 仅确认连接请求          			|
| reverseRequest  	| 	   3        	| Length(4B) + Data     		| Length 是 Data 的字节数		|
| reverseAnswer   	| 	   4        	| Length(4B) + reverseData 	| Length 是反转后数据的字节数	|
---------------------------------------------------------------------------------------------------
所有整数字段均采用大端序（Big-Endian）

四、命令行参数说明
------------------
【服务器端】
    python server.py [--host HOST] [--port PORT]
    
    --host  监听IP地址，默认 0.0.0.0（监听所有网卡）
    --port  监听端口，默认 12345

【客户端】
    python client.py serverIP serverPort Lmin Lmax inputFile outputFile [--chunk-seed SEED]
    
    --serverIP    服务器IP地址
    --serverPort  服务器端口号
    --Lmin        最小分块长度
    --Lmax        最大分块长度
    --inputFile   输入文件路径（待反转的文件）
    --outputFile  输出文件路径（反转后的结果）
    --chunk-seed 分块随机种子，默认 42（确保分块结果可复现）

五、运行示例
------------
1. 启动服务器（终端1）:
   python server.py --port 12345

2. 运行客户端（终端2）:
   python client.py 192.168.34.129 12345 10 40 test_input.txt test_output.txt

3. 验证并发（再开一个终端3）:
   python client.py 192.168.34.129 12345 10 40 test_input1.txt test_output1.txt 

六、核心算法说明
----------------
【分块算法】
1. 读取输入文件的所有字节，得到总长度 total_len
2. 用指定的 chunk_seed 初始化 random.Random()，确保分块结果可复现
3. 循环生成每一块的长度：
   - 在 [Lmin, Lmax] 之间随机取数
   - 如果剩余字节数 < Lmin，则最后一块取剩余所有字节
   - 否则取 min(随机数, 剩余字节数) 作为块长度
4. 统计总块数 N，保存每一块的起始偏移和长度
5. 客户端发送 Initialization 报文时携带 N，服务器据此循环处理 N 个 reverseRequest

【整体反转实现】
服务器对每一块数据进行字节级反转（如 "abc" -> "cba"）后返回。
客户端收到所有反转块后，按块索引的逆序拼接：
- 第 N 块（文件末尾）的反转结果放在输出文件最前面
- 第 1 块（文件开头）的反转结果放在输出文件最后面
这样最终输出就是原始文件的完全整体反转。

例如：原始文件 "123890"
  分块假设为 ["123", "890"]
  服务器返回：["321", "098"]
  客户端逆序拼接："098" + "321" = "098321"
  这正是原始文件的完全整体反转！

七、多线程处理说明
------------------
- 服务器主线程循环 accept() 等待连接
- 每 accept 一个客户端连接，立即创建一个新线程处理该客户端
- 使用 threading.Thread(daemon=True) 确保主线程退出时子线程自动结束

八、日志实现说明
----------------
- 每次收发报文都记录到 run_log.txt
- 日志格式: [YYYY-MM-DD HH:MM:SS] [角色] 动作 | Type=X, 字段=值, 长度=XB | 来源/目标
- 时间精确到秒，可与 Wireshark 抓包时间对应验证

九、Wireshark 抓包验证
----------------------
1. 启动 Wireshark，选择对应的网卡接口
2. 设置过滤条件: tcp.port == 12345
3. 运行服务器和客户端进行通信
4. 在 Wireshark 中可观察到 4 种报文类型：
   - Initialization (Type=1, 6 bytes)
   - agree (Type=2, 2 bytes)
   - reverseRequest (Type=3, 6+Length bytes)
   - reverseAnswer (Type=4, 6+Length bytes)
5. 对比 run_log.txt 中的时间和 Wireshark 抓包时间，验证一致性

十、掌握的知识点
----------------
1. TCP Socket 编程基础：socket()、bind()、listen()、accept()、connect()、sendall()、recv()
2. 字节序处理：struct 模块的 pack/unpack，大端序网络字节序
3. 可靠数据传输：recv_all() 函数确保接收指定字节数
4. 多线程并发：threading 模块实现多客户端同时处理
5. 线程同步：通过文件锁保证写入日志不会发生覆盖、错乱
6. 报文协议设计：自定义协议，定义报文类型和字段格式
7. 文件分块与整体反转：随机分块算法、逆序拼接实现整体反转
8. 日志记录：时间、报文类型、数据长度