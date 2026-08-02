import { useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { CheckCircle2, AlertTriangle, XCircle, Send, Loader2, Moon, Sun } from "lucide-react";
import { useTheme } from "@/components/ThemeProvider";

const DEMO_EXAMPLES = [
  {
    label: "Example 1 (100/100)",
    text: "[DEMO_GREEN] Members are hereby notified of revised surveillance measures applicable to securities in the SME segment with effect from the settlement cycle commencing 20 July 2026.",
    mockResponse: {
      verdict: "GREEN",
      trust_score: 100,
      headline: "Verified. This communication is cryptographically sealed and present in the PRAMAAN transparency log.",
      reasons: [
        { code: "SEALED", severity: "info", message: "Sealed by National Stock Exchange of India (SEBI Reg. MII-NSE-0001). Present in the transparency log at index 42." }
      ],
      sealed: true,
      latency_note: "Resolved by seal check alone — no model inference required.",
      latency_ms: 12
    }
  },
  {
    label: "Example 2 (50/100)",
    text: "[DEMO_AMBER] URGENT: The board will meet on Thursday to approve the quarterly results. Act fast!",
    mockResponse: {
      verdict: "AMBER",
      trust_score: 50,
      headline: "Unverified. This content carries no cryptographic seal and shows some risk indicators. Proceed with caution.",
      reasons: [
        { code: "URGENCY_PRESSURE", severity: "warning", message: "Manufactured urgency or scarcity — a standard coercion pattern. [matched: \"Act fast!\"]" }
      ],
      sealed: false,
      latency_note: "Full multimodal analysis path.",
      latency_ms: 184
    }
  },
  {
    label: "Example 3 (0/100)",
    text: "[DEMO_RED] OFFICIAL SEBI CIRCULAR: Priority IPO allotment approved for select investors. Guaranteed 200% returns! Pay to upi@okaxis now.",
    mockResponse: {
      verdict: "RED",
      trust_score: 0,
      headline: "High risk. Multiple fraud indicators detected. Do not act on this message.",
      reasons: [
        { code: "NOT_IN_LOG", severity: "critical", message: "This content presents itself as an official communication, but it does not appear in the transparency log. It was never issued." },
        { code: "GUARANTEED_RETURNS", severity: "critical", message: "Promises assured or guaranteed returns. No SEBI-registered entity may guarantee returns. [matched: \"Guaranteed 200% returns\"]" },
        { code: "OFF_PLATFORM_PAYMENT", severity: "critical", message: "Solicits payment to a personal UPI ID, wallet or account. [matched: \"upi@okaxis\"]" }
      ],
      sealed: false,
      latency_note: "Full multimodal analysis path.",
      latency_ms: 215
    }
  }
];

interface Reason {
  code: string;
  severity: "info" | "warning" | "critical";
  message: string;
}

interface Assessment {
  verdict: "GREEN" | "AMBER" | "RED";
  trust_score: number;
  headline: string;
  reasons: Reason[];
  sealed: boolean;
  seal_entry?: any;
  latency_note: string;
  latency_ms?: number;
}

interface Message {
  id: string;
  sender: "user" | "bot";
  text?: string;
  assessment?: Assessment;
  isLoading?: boolean;
}

export default function Verify() {
  const { theme, setTheme } = useTheme();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      sender: "bot",
      text: "Hi! I am PRAMAAN. Send me a forward, circular text, or URL, and I will verify its authenticity.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);

  const handleSend = async (text: string, isDemo = false, mockData?: any) => {
    // If it's a demo string, extract the actual text for display
    const displayText = text.replace(/\[DEMO_(GREEN|AMBER|RED)\] /, "");
    if (!displayText.trim()) return;

    const userMsg: Message = { id: Date.now().toString(), sender: "user", text: displayText };
    const botLoadingMsg: Message = { id: (Date.now() + 1).toString(), sender: "bot", isLoading: true };
    
    setMessages((prev) => [...prev, userMsg, botLoadingMsg]);
    setInput("");
    setIsTyping(true);

    const startTime = performance.now();
    try {
      let assessment;

      if (isDemo && mockData) {
        // Use exact mock data for the 100/50/0 showcase
        await new Promise(resolve => setTimeout(resolve, 400)); // Simulate network
        assessment = mockData;
      } else {
        // Send to real backend
        const res = await axios.post("/api/v1/verify", { content: text });
        const latencyMs = Math.round(performance.now() - startTime);
        assessment = { ...res.data, latency_ms: latencyMs };
      }
      
      setMessages((prev) => 
        prev.map((msg) => (msg.id === botLoadingMsg.id ? { ...msg, isLoading: false, assessment } : msg))
      );
    } catch (error) {
      console.error(error);
      setMessages((prev) => 
        prev.map((msg) => 
          msg.id === botLoadingMsg.id 
            ? { ...msg, isLoading: false, text: "Sorry, I encountered an error verifying that message. Is the backend running?" } 
            : msg
        )
      );
    } finally {
      setIsTyping(false);
    }
  };

  const getVerdictGradient = (verdict: string) => {
    switch (verdict) {
      case "GREEN": return "from-[#00A870]/20 to-[#00A870]/5 border-[#00A870]/30";
      case "AMBER": return "from-[#E9B949]/20 to-[#E9B949]/5 border-[#E9B949]/30";
      case "RED": return "from-[#D6353B]/20 to-[#D6353B]/5 border-[#D6353B]/30";
      default: return "from-gray-500/20 to-gray-500/5 border-gray-500/30";
    }
  };

  const getVerdictIcon = (verdict: string) => {
    switch (verdict) {
      case "GREEN": return <CheckCircle2 className="w-5 h-5 text-[#00A870]" />;
      case "AMBER": return <AlertTriangle className="w-5 h-5 text-[#E9B949]" />;
      case "RED": return <XCircle className="w-5 h-5 text-[#D6353B]" />;
      default: return null;
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "critical": return "text-[#D6353B] bg-[#D6353B]/10 border-[#D6353B]/20";
      case "warning": return "text-[#E9B949] bg-[#E9B949]/10 border-[#E9B949]/20";
      case "info": return "text-blue-500 bg-blue-500/10 border-blue-500/20";
      default: return "text-gray-500 bg-gray-500/10 border-gray-500/20";
    }
  };

  return (
    <div className="flex flex-col h-screen max-w-4xl mx-auto border-x bg-background/50 backdrop-blur-3xl shadow-2xl relative overflow-hidden transition-colors duration-300">
      
      {/* Background gradients */}
      <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-primary/10 blur-[100px] pointer-events-none z-0" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-[#00A870]/10 blur-[100px] pointer-events-none z-0" />

      {/* Header */}
      <header className="bg-card/80 backdrop-blur-md border-b p-4 shadow-sm z-10 flex items-center justify-between sticky top-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center font-serif text-xl font-bold text-primary-foreground shadow-lg shadow-primary/20">
            P
          </div>
          <div>
            <h1 className="font-serif font-bold text-lg text-foreground tracking-wide">PRAMAAN</h1>
            <p className="text-xs text-muted-foreground font-medium">Securities Market TechSprint</p>
          </div>
        </div>
        <Button 
          variant="ghost" 
          size="icon" 
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          className="rounded-full hover:bg-muted"
        >
          {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </Button>
      </header>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 z-10 scroll-smooth">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"} animate-in fade-in slide-in-from-bottom-4 duration-500`}>
            
            <div className={`
              max-w-[85%] rounded-3xl p-5 shadow-sm relative
              ${msg.sender === "user" 
                ? "bg-primary text-primary-foreground rounded-br-sm shadow-primary/20" 
                : msg.assessment
                  ? `bg-gradient-to-br ${getVerdictGradient(msg.assessment.verdict)} border rounded-bl-sm backdrop-blur-md shadow-lg`
                  : "bg-card border rounded-bl-sm"
              }
            `}>
              {msg.isLoading ? (
                <div className="flex items-center gap-2 text-muted-foreground font-medium">
                  <Loader2 className="w-4 h-4 animate-spin" /> Verifying securely...
                </div>
              ) : msg.assessment ? (
                <div className="space-y-4">
                  {/* Assessment Header */}
                  <div className="flex items-center justify-between gap-3">
                    <Badge variant="outline" className="bg-background/50 backdrop-blur-sm border-muted/50 px-3 py-1.5 shadow-sm flex items-center gap-2 rounded-full">
                      {getVerdictIcon(msg.assessment.verdict)}
                      <span className="font-mono font-bold tracking-tight text-sm">
                        SCORE: {msg.assessment.trust_score}/100
                      </span>
                    </Badge>
                    <span className="font-mono text-xs bg-background/50 px-2 py-1 rounded-md text-muted-foreground border">
                      {msg.assessment.latency_ms}ms
                    </span>
                  </div>
                  
                  <h3 className="font-serif font-semibold text-lg text-foreground leading-snug">
                    {msg.assessment.headline}
                  </h3>

                  {/* Expandable Reasons */}
                  {msg.assessment.reasons.length > 0 && (
                    <Accordion {...{ type: "single", collapsible: true } as any} className="w-full">
                      <AccordionItem value="reasons" className="border-t border-muted/30 mt-2">
                        <AccordionTrigger className="py-3 text-sm font-medium hover:no-underline text-muted-foreground hover:text-foreground transition-colors">
                          View Analysis ({msg.assessment.reasons.length} signals)
                        </AccordionTrigger>
                        <AccordionContent className="space-y-3 pt-2">
                          {msg.assessment.reasons.map((r, i) => (
                            <div key={i} className="flex flex-col gap-1.5 text-sm bg-background/60 p-3.5 rounded-xl border border-muted/50 shadow-sm">
                              <span className={`w-fit font-bold text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-md border ${getSeverityColor(r.severity)}`}>
                                {r.code.replace(/_/g, ' ')}
                              </span>
                              <span className="text-foreground/90 font-medium leading-relaxed">{r.message}</span>
                            </div>
                          ))}
                        </AccordionContent>
                      </AccordionItem>
                    </Accordion>
                  )}
                  
                  {/* Latency Note */}
                  <div className="text-xs text-muted-foreground pt-3 border-t border-muted/30">
                    <span className="italic">{msg.assessment.latency_note}</span>
                  </div>
                </div>
              ) : (
                <p className="text-sm md:text-base leading-relaxed font-medium">{msg.text}</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Input Area */}
      <div className="bg-card/80 backdrop-blur-md p-4 sm:p-6 border-t shadow-lg z-10">
        <div className="mb-4">
          <p className="text-[10px] text-muted-foreground mb-2 font-bold uppercase tracking-widest flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
            Demo Scenarios
          </p>
          <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
            {DEMO_EXAMPLES.map((ex, i) => (
              <Button 
                key={i} 
                variant="outline" 
                size="sm"
                className="whitespace-nowrap shrink-0 text-xs font-semibold rounded-full border-muted-foreground/20 hover:border-primary hover:bg-primary/5 transition-all shadow-sm"
                onClick={() => handleSend(ex.text, true, ex.mockResponse)}
                disabled={isTyping}
              >
                {ex.label}
              </Button>
            ))}
          </div>
        </div>
        
        <div className="flex items-center gap-3 relative">
          <input
            type="text"
            className="flex-1 border-2 border-muted bg-background/50 rounded-full px-5 py-3 text-sm focus:outline-none focus:border-primary focus:ring-4 focus:ring-primary/10 transition-all text-foreground placeholder:text-muted-foreground/70"
            placeholder="Type a message or paste a URL to verify..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend(input)}
            disabled={isTyping}
          />
          <Button 
            className="rounded-full w-12 h-12 p-0 bg-primary hover:bg-primary/90 text-primary-foreground shadow-lg shadow-primary/30 flex-shrink-0 transition-transform active:scale-95"
            onClick={() => handleSend(input)}
            disabled={isTyping || !input.trim()}
          >
            <Send className="w-5 h-5 ml-1" />
          </Button>
        </div>
      </div>
    </div>
  );
}
