setwd("/working/directory/path")

library(ggplot2)
library(ggpubr)
library(ggbeeswarm)

data <- read.table("Residence-Time.csv", sep=',', header = TRUE)
data$Cell.Line <- factor(data$Cell.Line, levels = c("WT", "Empty", "dOB", "K90E"))
comparison <- list( c("WT", "Empty"), c("dOB", "WT"),
                    c("WT", "K90E"))

p <- ggboxplot(data, x = "Cell.Line", y = "Time",
               color = "Cell.Line", palette = "jco") + 
  geom_quasirandom(aes(color = Cell.Line)) + 
  xlab("Cell Line") + ylab("Residence Time (sec)\n(Long interaction)") + 
  labs(color = "Cell Line") + ggtitle("Residence Time") + 
  stat_compare_means(comparisons = comparison, method = "t.test")

data <- read.table("Colocalization.csv", sep=',', header = TRUE)
data$Percent.Stable <- as.numeric(data$Percent.Stable)
data$Cell.Line <- factor(data$Cell.Line, levels = c("WT", "Empty", "DOB", "K90E"))

comparison <- list( c("WT", "Empty"), c("WT", "DOB"),
                    c("WT", "K90E"))

q <- ggboxplot(data, x = "Cell.Line", y = "Percent.Stable",
               color = "Cell.Line", palette = "jco",
               add = "jitter") + 
  xlab("Cell Line") + ylab("% of Telomese with hTR\n(Long interaction)") + 
  labs(color = "Cell Line") + ggtitle("Telomere hTR Interaction") + 
  stat_compare_means(comparisons = comparison, method = "t.test")

ggarrange(q, p, common.legend = TRUE, legend="bottom")
ggsave("Residence-Interaction.pdf", units = "in", width=10, height=6)
