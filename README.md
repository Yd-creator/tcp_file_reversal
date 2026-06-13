# tcp_file_reversal
TCP实现数据反转

一、运行环境

Python 版本: Python 3.10+

依赖: 仅使用 Python 标准库 (socket, threading, struct, argparse, random, time, os)

操作系统: Windows 、虚拟机VMware上的ubuntu中运行

二、命令行参数说明

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
