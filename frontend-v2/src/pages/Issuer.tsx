import { useState, useEffect } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, Copy, CheckCircle2, ShieldCheck, GitCommit } from "lucide-react";

interface IssuerInfo {
  did: string;
  name: string;
  sebi_reg_no: string;
  category: string;
}

export default function Issuer() {
  const [issuers, setIssuers] = useState<IssuerInfo[]>([]);
  const [selectedIssuer, setSelectedIssuer] = useState("");
  const [artefactType, setArtefactType] = useState("circular");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    axios.get("/api/v1/issuers").then((res) => {
      setIssuers(res.data);
      if (res.data.length > 0) {
        setSelectedIssuer(res.data[0].did);
      }
    }).catch(console.error);
  }, []);

  const handleSeal = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setResult(null);
    setCopied(false);
    try {
      const res = await axios.post("/api/v1/seal", {
        issuer_did: selectedIssuer,
        content: content,
        artefact_type: artefactType,
        title: title
      });
      setResult(res.data);
    } catch (error) {
      console.error(error);
      alert("Failed to seal artefact.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const copySignature = () => {
    if (result?.entry?.signature_hex) {
      navigator.clipboard.writeText(result.entry.signature_hex);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-[#0B1B3A] text-white p-4 shadow-md flex justify-between items-center">
        <div className="flex items-center gap-3">
          <ShieldCheck className="w-8 h-8 text-[#00A870]" />
          <div>
            <h1 className="font-serif font-bold text-xl">Issuer Console</h1>
            <p className="text-xs text-blue-200">Seal & Append at Source</p>
          </div>
        </div>
      </header>

      <main className="flex-1 p-6 max-w-6xl w-full mx-auto grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
        <Card className="shadow-sm border-t-4 border-t-[#0B1B3A]">
          <CardHeader>
            <CardTitle className="font-serif">New Artefact</CardTitle>
            <CardDescription>Issue a new document directly to the PRAMAAN transparency log.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSeal} className="space-y-4">
              <div className="space-y-2">
                <Label>Issuer</Label>
                <Select value={selectedIssuer} onValueChange={setSelectedIssuer}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select issuer" />
                  </SelectTrigger>
                  <SelectContent>
                    {issuers.map(i => (
                      <SelectItem key={i.did} value={i.did}>
                        {i.name} ({i.sebi_reg_no})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Artefact Type</Label>
                <Select value={artefactType} onValueChange={setArtefactType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="circular">Circular</SelectItem>
                    <SelectItem value="announcement">Announcement</SelectItem>
                    <SelectItem value="filing">Filing</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Title</Label>
                <Input required value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. NSE/SURV/2026/041" />
              </div>

              <div className="space-y-2">
                <Label>Body Content</Label>
                <Textarea 
                  required 
                  className="min-h-[150px] font-mono text-sm" 
                  value={content} 
                  onChange={e => setContent(e.target.value)} 
                  placeholder="Enter the official text here..."
                />
              </div>

              <Button type="submit" disabled={isSubmitting} className="w-full bg-[#00A870] hover:bg-[#008f5f] text-white">
                {isSubmitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ShieldCheck className="w-4 h-4 mr-2" />}
                Sign & Seal to Log
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Results Panel */}
        <div className="space-y-6">
          <Card className="bg-[#0B1B3A] text-white border-none shadow-xl">
            <CardHeader>
              <CardTitle className="font-serif text-[#E9B949] flex items-center gap-2">
                <GitCommit className="w-5 h-5" />
                Transparency Log
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-48 relative border-2 border-dashed border-blue-800 rounded-xl bg-blue-950/50 flex flex-col items-center justify-center overflow-hidden">
                {!result ? (
                  <p className="text-blue-300/60 text-sm font-medium">Waiting for new artefact...</p>
                ) : (
                  <div className="flex flex-col items-center animate-in fade-in slide-in-from-bottom-8 duration-700">
                    <div className="w-12 h-12 rounded-full bg-[#00A870]/20 border-2 border-[#00A870] flex items-center justify-center mb-2 shadow-[0_0_15px_rgba(0,168,112,0.5)]">
                      <ShieldCheck className="text-[#00A870] w-6 h-6" />
                    </div>
                    <Badge className="bg-[#00A870] hover:bg-[#00A870] text-white border-none mb-1 text-xs">
                      Index #{result.entry.index} Appended
                    </Badge>
                    <p className="text-xs font-mono text-blue-200 mt-2 truncate w-48 text-center opacity-70">
                      {result.entry.hash.substring(0, 16)}...
                    </p>
                    
                    {/* Tree lines visual */}
                    <div className="absolute bottom-0 w-px h-8 bg-gradient-to-t from-blue-800 to-transparent"></div>
                    <div className="absolute bottom-4 -left-10 w-full h-px bg-gradient-to-r from-transparent via-blue-800 to-transparent"></div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {result && (
            <Card className="animate-in fade-in duration-500 shadow-sm border-l-4 border-l-[#00A870]">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg flex items-center justify-between">
                  Cryptographic Proof
                  {result.signature_valid && <Badge variant="outline" className="text-[#00A870] border-[#00A870] bg-[#00A870]/10">Verified</Badge>}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label className="text-xs text-gray-500 uppercase tracking-wider">Content Hash (SHA-256)</Label>
                  <p className="font-mono text-xs bg-gray-100 p-2 rounded break-all text-gray-700 mt-1">
                    {result.entry.hash}
                  </p>
                </div>
                
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <Label className="text-xs text-gray-500 uppercase tracking-wider">Ed25519 Signature</Label>
                    <Button variant="ghost" size="sm" className="h-6 text-xs px-2" onClick={copySignature}>
                      {copied ? <CheckCircle2 className="w-3 h-3 mr-1 text-[#00A870]" /> : <Copy className="w-3 h-3 mr-1" />}
                      {copied ? "Copied" : "Copy Full"}
                    </Button>
                  </div>
                  <p className="font-mono text-xs bg-gray-100 p-2 rounded break-all text-gray-700">
                    {result.entry.signature_hex.substring(0, 32)}...
                    <span className="text-gray-400"> (truncated)</span>
                  </p>
                </div>

                <div>
                  <Label className="text-xs text-gray-500 uppercase tracking-wider">New Merkle Root</Label>
                  <p className="font-mono text-xs bg-gray-100 p-2 rounded break-all text-[#0B1B3A] font-semibold mt-1">
                    {result.signed_tree_head.root_hash}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">Tree Size: {result.signed_tree_head.tree_size}</p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </main>
    </div>
  );
}
