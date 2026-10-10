#include <linux/rtc.h>
#include <stdio.h>
int main(void) {
    printf("%zu %zu %lx %lx %lx %lx\n", sizeof(struct rtc_time),
           sizeof(struct rtc_wkalrm), (unsigned long)RTC_RD_TIME,
           (unsigned long)RTC_WKALM_RD, (unsigned long)RTC_WKALM_SET,
           (unsigned long)RTC_AIE_OFF);
    return 0;
}
