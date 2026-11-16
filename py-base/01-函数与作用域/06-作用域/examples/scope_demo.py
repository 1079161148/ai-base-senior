"""第 06 章示例：局部/全局作用域与闭包。"""

call_count = 0

def record_call():
    """用 global 显式声明后才赋值模块级名字 [R1]。"""
    global call_count
    call_count = call_count + 1
    local_value = call_count
    return local_value

def outer():
    """内层函数引用包含作用域的名字 [R1]。"""
    prefix = "call-"
    def inner(number):
        return prefix + str(number)
    return inner(2)

print("第 1 次:", record_call())
print("第 2 次:", record_call())
print("模块级计数:", call_count)
print("闭包:", outer())
