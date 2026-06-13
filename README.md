# tcp_file_reversal
TCP实现数据反转
一、运行环境
Python 版本: Python 3.10+
依赖: 仅使用 Python 标准库 (socket, threading, struct, argparse, random, time, os)
操作系统: Windows 、虚拟机VMware上的ubuntu中运行

二、文件说明
server.py             - TCP 服务器端程序，支持多线程并发处理多个客户端
client.py              - TCP 客户端程序，支持分块发送、接收反转数据、逆序拼接实现整体反转
test_input.txt      - 全英文ASCII字符测试文件
run_log.txt          - 运行时自动生成的日志文件（记录所有收发报文的时间和类型）
test_output.txt   - 保存服务器端反转后的数据

三、报文格式（大端序）
--------------------------------------------------------------------------------------------
|      报文类型      |    Type(2B) 	| 		其他字段             | 			说明            |
|-------------------|--------------	|---------------------------|---------------------------|
| Initialization    |      1       	| N(4B)                 	| N 是要反转的总块数      	|
| agree             | 	   2        | 无                    	| 仅确认连接请求          	|
| reverseRequest  	| 	   3        | Length(4B) + Data     	| Length 是 Data 的字节数	|
| reverseAnswer   	| 	   4        | Length(4B) + reverseData 	| Length 是反转后数据的字节数 |
---------------------------------------------------------------------------------------------
所有整数字段均采用大端序（Big-Endian）

四、命令行参数说明
------------------
【服务器端】
    python3 server.py [--port PORT]（虚拟机中为python3）
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
   python3 server.py --port 12345

2. 运行客户端（终端2）:
   python client.py 192.168.34.129 12345 10 40 test_input.txt test_output.txt

3. 验证并发（再开一个终端3）:
   python client.py 192.168.34.129 12345 10 40 test_input1.txt test_output1.txt 

六、核心算法说明
----------------
【分块算法】
1. 读取输入文件的所有字节，得到总长度total_len
2. 用指定的chunk_seed初始化random.Random()，确保分块结果可复现
3. 循环生成每一块的长度：
   - 在[Lmin, Lmax]之间随机取数
   - 如果剩余字节数<Lmin，则最后一块取剩余所有字节
   - 否则取min(随机数, 剩余字节数) 作为块长度
4. 统计总块数N，保存每一块的起始偏移和长度
5. 客户端发送Initialization报文时携带N，服务器据此循环处理N个reverseRequest

【整体反转实现】
服务器对每一块数据进行字节级反转（如 "abc" -> "cba"）后返回。
客户端收到所有反转块后，按块索引的逆序拼接：
- 第 N 块（文件末尾）的反转结果放在输出文件最前面
- 第 1 块（文件开头）的反转结果放在输出文件最后面
这样最终输出就是原始文件的完全整体反转。

