p = 'C:/Users/67972/projects/short-drama-training/training_panel.html'
s = open(p, encoding='utf-8').read()
import re
print('size=', len(s.encode('utf-8')))
print('<img            =', s.count('<img'))
thumb = s.count('data-role="thumb"') - s.count("closest('[data-role=\"thumb\"]')")
print('data-role=thumb =', thumb)  # 应为 54
print('unique wXX_Y    =', len(set(re.findall(r'w\d{2}_\d\.png', s))))  # 应为 54
print('base64 count    =', s.count('data:image/'))  # 应为 0
print('zh 同一个齐肩黑发 =', s.count('同一个齐肩黑发'))  # 应为 54
print('data-writing uniq=', len(set(re.findall(r'data-writing="(\d+)"', s))))  # 应为 27
print('exp-note 存在    =', 'exp-note' in s)  # 应为 True
print('这批图在测什么   =', '这批图在测什么' in s)  # 应为 True
print('lightbox/双图优/主图/备选/弃 均在 =', all(x in s for x in ['lightbox', '双图优', '主图', '备选', '弃']))
